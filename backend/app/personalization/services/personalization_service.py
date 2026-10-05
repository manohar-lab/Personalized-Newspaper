"""personalization_service.py — Multi-Factor Personalization Engine Service.

Coordinates user interest loading, user embedding caching, article scoring,
multi-factor ranking, diversity optimization, and personalized newspaper generation.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.models.article import Article
from app.models.topic import Topic
from app.models.interest import UserInterest
from app.repositories.article_repository import ArticleRepository
from app.repositories.action_repository import ActionRepository
from app.schemas.article import ArticleBase, TopicSummary
from app.schemas.newspaper import (
    EditionInfo,
    UserSummary,
    NewspaperSection,
    NewspaperResponse,
)
from app.personalization.schemas import (
    RelevanceScoreBreakdown,
    UserInterestProfile,
    ScoredArticle,
)
from app.personalization.scoring.relevance_scorer import RelevanceScorer
from app.personalization.services.user_embedding_service import UserEmbeddingService

logger = logging.getLogger(__name__)


class PersonalizationService:
    """Core personalization engine orchestrating scoring, ranking, and newspaper curation."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.article_repo = ArticleRepository(session)
        self.action_repo = ActionRepository(session)
        self.user_embedding_service = UserEmbeddingService(session)
        self.scorer = RelevanceScorer()

    async def get_user_interest_profile(self, user_id: uuid.UUID) -> UserInterestProfile:
        """Fetch user explicit interests and cached semantic embedding vector."""
        stmt = (
            select(UserInterest)
            .options(selectinload(UserInterest.topic))
            .where(UserInterest.user_id == user_id)
            .order_by(UserInterest.created_at.desc())
        )
        result = await self.session.execute(stmt)
        interests = list(result.scalars().all())

        positive_interests: Dict[str, float] = {}
        negative_interests: Dict[str, float] = {}
        topic_names_map: Dict[str, str] = {}
        topic_ids_map: Dict[str, uuid.UUID] = {}

        for ui in interests:
            slug = ui.topic.slug
            topic_names_map[slug] = ui.topic.name
            topic_ids_map[slug] = ui.topic.id

            if ui.preference_type == "POSITIVE":
                positive_interests[slug] = float(ui.interest_score)
            elif ui.preference_type == "NEGATIVE":
                negative_interests[slug] = float(ui.interest_score)

        has_interests = bool(positive_interests or negative_interests)

        user_embedding: Optional[List[float]] = None
        if positive_interests:
            user_embedding = await self.user_embedding_service.get_or_create_user_embedding(
                user_id=user_id,
                positive_interests=positive_interests,
                topic_names_map=topic_names_map,
            )

        return UserInterestProfile(
            user_id=user_id,
            positive_interests=positive_interests,
            negative_interests=negative_interests,
            topic_names_map=topic_names_map,
            topic_ids_map=topic_ids_map,
            embedding=user_embedding,
            has_interests=has_interests,
        )

    async def calculate_article_relevance(
        self,
        user_id: uuid.UUID,
        article_id: uuid.UUID,
    ) -> Tuple[float, RelevanceScoreBreakdown]:
        """Compute personal relevance score and breakdown for a single article."""
        profile = await self.get_user_interest_profile(user_id)

        # Query article with all required relationships loaded
        stmt = (
            select(Article)
            .where(Article.id == article_id)
            .options(
                selectinload(Article.topics),
                selectinload(Article.analysis),
                selectinload(Article.entities),
                selectinload(Article.keywords),
            )
        )
        result = await self.session.execute(stmt)
        article = result.scalar_one_or_none()

        if not article:
            raise ValueError(f"Article with id {article_id} not found")

        score, breakdown = self.scorer.compute_relevance(
            article=article,
            positive_interests=profile.positive_interests,
            negative_interests=profile.negative_interests,
            user_embedding=profile.embedding,
            positive_topic_names=list(profile.topic_names_map.values()),
        )
        return score, breakdown

    def apply_topic_diversity(
        self,
        scored_items: List[Tuple[Article, float, RelevanceScoreBreakdown]],
    ) -> List[Tuple[Article, float, RelevanceScoreBreakdown]]:
        """Re-orders scored articles to avoid clustering consecutive articles of the same topic."""
        if len(scored_items) <= 2:
            return scored_items

        def get_primary_topic(art: Article) -> Optional[str]:
            if art.topics:
                return art.topics[0].slug
            if art.analysis and art.analysis.primary_category:
                return art.analysis.primary_category.lower()
            return None

        remaining = list(scored_items)
        diversified: List[Tuple[Article, float, RelevanceScoreBreakdown]] = []

        # Start with the highest-scoring article
        diversified.append(remaining.pop(0))

        while remaining:
            last_topic = get_primary_topic(diversified[-1][0])
            best_idx = 0

            # If last article had a topic, look for highest scoring article with a DIFFERENT topic
            if last_topic is not None:
                found_diff = False
                for idx, (cand_art, cand_score, _) in enumerate(remaining):
                    cand_topic = get_primary_topic(cand_art)
                    if cand_topic != last_topic:
                        best_idx = idx
                        found_diff = True
                        break

                # If all remaining have same topic, fallback to top scored
                if not found_diff:
                    best_idx = 0

            diversified.append(remaining.pop(best_idx))

        return diversified

    async def rank_articles_for_user(
        self,
        user_id: uuid.UUID,
        articles: List[Article],
        apply_diversity: bool = True,
    ) -> List[Tuple[Article, float, RelevanceScoreBreakdown]]:
        """Rank a batch of candidate articles for a user using multi-factor scoring."""
        if not articles:
            return []

        profile = await self.get_user_interest_profile(user_id)
        now = datetime.now(timezone.utc)

        scored: List[Tuple[Article, float, RelevanceScoreBreakdown]] = []
        for art in articles:
            score, breakdown = self.scorer.compute_relevance(
                article=art,
                positive_interests=profile.positive_interests,
                negative_interests=profile.negative_interests,
                user_embedding=profile.embedding,
                positive_topic_names=list(profile.topic_names_map.values()),
                now=now,
            )
            # Filter out articles with extreme negative net score (< 0.05 when user has strong negative preference)
            if score > 0.0 or not profile.has_interests:
                scored.append((art, score, breakdown))

        # Sort descending by relevance score, with tie-break on publication date
        scored.sort(
            key=lambda x: (x[1], x[0].published_at.timestamp() if x[0].published_at else 0),
            reverse=True,
        )

        if apply_diversity and profile.has_interests:
            scored = self.apply_topic_diversity(scored)

        return scored

    async def build_personalized_newspaper(self, user: User) -> NewspaperResponse:
        """Assemble full personalized newspaper edition for user using the multi-factor engine."""
        profile = await self.get_user_interest_profile(user.id)

        # 1. Fetch published articles with all relationships eager-loaded
        stmt = (
            select(Article)
            .where(Article.status == "PUBLISHED")
            .options(
                selectinload(Article.topics),
                selectinload(Article.analysis),
                selectinload(Article.entities),
                selectinload(Article.keywords),
            )
        )
        result = await self.session.execute(stmt)
        all_articles = result.scalars().all()

        # 2. Fetch user actions (saved, liked, not interested)
        article_ids = [a.id for a in all_articles]
        actions_map = await self.action_repo.get_user_actions_map(user.id, article_ids)

        # 3. Filter out NOT_INTERESTED articles
        candidate_articles = [
            a for a in all_articles
            if "NOT_INTERESTED" not in actions_map.get(a.id, set())
        ]

        # 4. Rank candidate articles
        ranked_items = await self.rank_articles_for_user(
            user_id=user.id,
            articles=candidate_articles,
            apply_diversity=True,
        )

        # Helper to convert Article model to schema
        def to_schema(art: Article, rel_score: Optional[float] = None) -> ArticleBase:
            acts = actions_map.get(art.id, set())
            return ArticleBase(
                id=art.id,
                title=art.title,
                slug=art.slug,
                description=art.description,
                content=art.content,
                source_name=art.source_name,
                source_url=art.source_url,
                canonical_url=art.canonical_url,
                source_id=art.source_id,
                feed_id=art.feed_id,
                ingestion_method=art.ingestion_method,
                author=art.author,
                image_url=art.image_url,
                published_at=art.published_at,
                created_at=art.created_at,
                reading_time_minutes=art.reading_time_minutes,
                status=art.status,
                language=art.language,
                is_full_text_available=art.is_full_text_available,
                topics=[
                    TopicSummary(id=t.id, name=t.name, slug=t.slug)
                    for t in art.topics
                ],
                is_saved="SAVE" in acts,
                is_liked="LIKE" in acts,
                is_not_interested="NOT_INTERESTED" in acts,
                relevance_score=rel_score,
            )

        # 5. Lead / Featured article
        featured_article: Optional[ArticleBase] = None
        if ranked_items:
            lead_art, lead_score, _ = ranked_items[0]
            featured_article = to_schema(lead_art, lead_score)
        elif candidate_articles:
            lead_art = candidate_articles[0]
            featured_article = to_schema(lead_art, 0.0)

        # 6. Group into sections
        sections: List[NewspaperSection] = []
        now = datetime.now(timezone.utc)

        if profile.has_interests:
            for slug, topic_name in profile.topic_names_map.items():
                # Only positive topics get dedicated sections
                if slug not in profile.positive_interests:
                    continue

                matching = [
                    (art, score, bd) for art, score, bd in ranked_items
                    if any(t.slug == slug for t in art.topics)
                ]

                section_schemas = [to_schema(art, score) for art, score, _ in matching]
                topic_id = profile.topic_ids_map.get(slug, uuid.uuid4())

                sections.append(
                    NewspaperSection(
                        topic=TopicSummary(
                            id=topic_id,
                            name=topic_name,
                            slug=slug,
                        ),
                        total_articles=len(section_schemas),
                        articles=section_schemas,
                    )
                )
        else:
            # Fallback when user has no explicit interests: group by topic
            topic_groups: Dict[str, List[Tuple[Article, float]]] = {}
            topic_info: Dict[str, TopicSummary] = {}
            for item in ranked_items:
                art, score, _ = item
                for t in art.topics:
                    if t.slug not in topic_groups:
                        topic_groups[t.slug] = []
                        topic_info[t.slug] = TopicSummary(id=t.id, name=t.name, slug=t.slug)
                    topic_groups[t.slug].append((art, score))

            for slug, arts in topic_groups.items():
                sections.append(
                    NewspaperSection(
                        topic=topic_info[slug],
                        total_articles=len(arts),
                        articles=[to_schema(a, s) for a, s in arts],
                    )
                )

        # 7. Build curation summary
        if not profile.has_interests:
            curation_summary = "Set your interests to personalize your newspaper."
        else:
            topic_names = [profile.topic_names_map[s] for s in profile.positive_interests.keys() if s in profile.topic_names_map]
            if not topic_names:
                curation_summary = "Set your interests to personalize your newspaper."
            elif len(topic_names) == 1:
                curation_summary = f"Curated from your interest in {topic_names[0]}."
            elif len(topic_names) == 2:
                curation_summary = f"Curated from your interests in {topic_names[0]} and {topic_names[1]}."
            else:
                first_part = ", ".join(topic_names[:-1])
                curation_summary = f"Curated from your interests in {first_part}, and {topic_names[-1]}."

        display_name = (
            user.full_name
            or (user.profile.display_name if getattr(user, "profile", None) else None)
            or user.email.split("@")[0]
        )
        date_str = now.strftime("%A, %B %d, %Y")

        return NewspaperResponse(
            edition=EditionInfo(
                date=date_str,
                title="Your Personalized Newspaper",
                subtitle="Today's Curated Edition",
            ),
            user=UserSummary(
                id=user.id,
                name=display_name,
                email=user.email,
            ),
            curation_summary=curation_summary,
            has_interests=profile.has_interests,
            featured_article=featured_article,
            sections=sections,
        )
