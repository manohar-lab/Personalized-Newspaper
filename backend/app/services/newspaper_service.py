import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.article import Article
from app.repositories.article_repository import ArticleRepository
from app.repositories.action_repository import ActionRepository
from app.services.interest_service import InterestService
from app.schemas.article import ArticleBase, TopicSummary
from app.schemas.newspaper import (
    EditionInfo,
    UserSummary,
    NewspaperSection,
    NewspaperResponse,
)

class NewspaperService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.article_repo = ArticleRepository(session)
        self.action_repo = ActionRepository(session)

    def _format_curation_summary(self, topic_names: List[str]) -> str:
        if not topic_names:
            return "Your newspaper isn't personalized yet. Please set your interests to generate your custom edition."
        if len(topic_names) == 1:
            return f"Curated from your interest in {topic_names[0]}."
        if len(topic_names) == 2:
            return f"Curated from your interests in {topic_names[0]} and {topic_names[1]}."
        first_part = ", ".join(topic_names[:-1])
        return f"Curated from your interests in {first_part}, and {topic_names[-1]}."

    def _compute_relevance_score(
        self,
        article: Article,
        positive_interests: Dict[str, float],
        negative_interests: Dict[str, float],
    ) -> float:
        """
        Calculates deterministic relevance score:
        +1.0 * score for positive matching topics
        -1.0 * score for negative matching topics
        """
        score = 0.0
        for topic in article.topics:
            if topic.slug in positive_interests:
                score += 1.0 * positive_interests[topic.slug]
            if topic.slug in negative_interests:
                score -= 1.0 * negative_interests[topic.slug]
        return round(score, 4)

    async def get_personalized_newspaper(self, user: User) -> NewspaperResponse:
        # 1. Fetch user's interests
        user_interests = await InterestService.get_user_interests(
            self.session, user.id
        )

        positive_interests: Dict[str, float] = {}
        positive_topics_map: Dict[str, str] = {}  # slug -> name
        negative_interests: Dict[str, float] = {}

        for ui in user_interests:
            if ui.preference_type == "POSITIVE":
                positive_interests[ui.topic.slug] = ui.interest_score
                positive_topics_map[ui.topic.slug] = ui.topic.name
            elif ui.preference_type == "NEGATIVE":
                negative_interests[ui.topic.slug] = ui.interest_score

        has_interests = len(positive_interests) > 0

        # 2. Fetch all published articles
        all_articles = await self.article_repo.get_all_published()

        # 3. Fetch user actions map (saved, liked, not interested)
        article_ids = [a.id for a in all_articles]
        actions_map = await self.action_repo.get_user_actions_map(user.id, article_ids)

        # 4. Filter out NOT_INTERESTED articles
        candidate_articles = [
            a for a in all_articles
            if "NOT_INTERESTED" not in actions_map.get(a.id, set())
        ]

        # 5. Score candidate articles
        scored_articles: List[tuple[Article, float]] = []
        for art in candidate_articles:
            rel_score = self._compute_relevance_score(
                art, positive_interests, negative_interests
            )
            # Only include if net score >= 0
            if rel_score >= 0.0:
                scored_articles.append((art, rel_score))

        # Sort by relevance score descending, then published_at descending
        scored_articles.sort(
            key=lambda x: (x[1], x[0].published_at.timestamp()),
            reverse=True,
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

        # 6. Select Lead / Featured Article
        featured_article: Optional[ArticleBase] = None
        featured_article_id: Optional[uuid.UUID] = None

        if scored_articles:
            lead_art, lead_score = scored_articles[0]
            featured_article = to_schema(lead_art, lead_score)
            featured_article_id = lead_art.id
        elif candidate_articles:
            # Fallback to most recent published article
            lead_art = candidate_articles[0]
            featured_article = to_schema(lead_art, 0.0)
            featured_article_id = lead_art.id

        # 7. Group into dynamic sections based on user's positive topics
        sections: List[NewspaperSection] = []
        now = datetime.now(timezone.utc)

        if has_interests:
            for slug, topic_name in positive_topics_map.items():
                # Find articles matching this topic
                matching_articles = [
                    (art, score) for art, score in scored_articles
                    if any(t.slug == slug for t in art.topics)
                ]

                # We can include articles in the section even if it was lead, or prioritize non-lead
                section_article_schemas = [
                    to_schema(art, score)
                    for art, score in matching_articles
                ]

                # Find topic UUID
                topic_id = None
                for art, _ in matching_articles:
                    for t in art.topics:
                        if t.slug == slug:
                            topic_id = t.id
                            break
                    if topic_id:
                        break

                if not topic_id:
                    # Look up from user_interests
                    for ui in user_interests:
                        if ui.topic.slug == slug:
                            topic_id = ui.topic.id
                            break

                sections.append(
                    NewspaperSection(
                        topic=TopicSummary(
                            id=topic_id or uuid.uuid4(),
                            name=topic_name,
                            slug=slug,
                        ),
                        total_articles=len(section_article_schemas),
                        articles=section_article_schemas,
                    )
                )
        else:
            # When user has no interests, group published articles by their primary topic
            topic_groups: Dict[str, List[Article]] = {}
            topic_info: Dict[str, TopicSummary] = {}
            for art in candidate_articles:
                for t in art.topics:
                    if t.slug not in topic_groups:
                        topic_groups[t.slug] = []
                        topic_info[t.slug] = TopicSummary(id=t.id, name=t.name, slug=t.slug)
                    topic_groups[t.slug].append(art)

            for slug, arts in topic_groups.items():
                sections.append(
                    NewspaperSection(
                        topic=topic_info[slug],
                        total_articles=len(arts),
                        articles=[to_schema(a, 0.0) for a in arts],
                    )
                )

        # 8. Build response
        display_name = user.full_name or (user.profile.display_name if user.profile else None) or user.email.split("@")[0]
        date_str = now.strftime("%A, %B %d, %Y")

        summary_names = list(positive_topics_map.values())
        curation_summary = self._format_curation_summary(summary_names)

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
            has_interests=has_interests,
            featured_article=featured_article,
            sections=sections,
        )
