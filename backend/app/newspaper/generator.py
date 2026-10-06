import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.models.article import Article
from app.newspaper.models import NewspaperEdition, NewspaperStory
from app.newspaper.candidate_selector import CandidateSelector
from app.newspaper.story_clusterer import StoryClusterer
from app.newspaper.editorial_scorer import EditorialScorer
from app.newspaper.lead_story_selector import LeadStorySelector
from app.newspaper.diversity import DiversityFilter
from app.newspaper.section_builder import SectionBuilder
from app.newspaper.schemas import (
    NewspaperEditionResponse,
    NewspaperSectionResponse,
    NewspaperStoryResponse,
    ControlledSection,
    StoryLayoutType,
)
from app.repositories.action_repository import ActionRepository

logger = logging.getLogger(__name__)


class NewspaperGenerationService:
    """
    Intelligent Personal Newspaper Generator.
    Transforms a pool of personalized articles into a coherent, structured, persistent daily edition.
    
    Pipeline:
      1. Load user & interest profile
      2. Fetch & filter candidate articles (24h primary with 72h fallback)
      3. Compute personal relevance
      4. Story clustering (multi-source deduplication)
      5. Editorial scoring (relevance + importance + recency + quality)
      6. Select user-specific lead story
      7. Apply topic & entity diversity rules
      8. Build controlled sections & assign layouts (LEAD, FEATURE, STANDARD, COMPACT)
      9. Persist snapshot edition
      10. Return formatted edition response
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.candidate_selector = CandidateSelector(session)
        self.story_clusterer = StoryClusterer(session)
        self.editorial_scorer = EditorialScorer()
        self.lead_selector = LeadStorySelector()
        self.diversity_filter = DiversityFilter()
        self.section_builder = SectionBuilder()
        self.action_repo = ActionRepository(session)

    async def get_or_generate_today_edition(self, user: User) -> NewspaperEditionResponse:
        """
        Returns today's persistent newspaper edition.
        If today's edition has already been generated, returns the stored snapshot.
        Otherwise, triggers generation for today.
        """
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        existing = await self.get_edition_by_date(user.id, today_str)
        if existing:
            return existing
        return await self.generate_daily_edition(user, today_str)

    async def get_edition_by_date(
        self, user_id: uuid.UUID, edition_date: str
    ) -> Optional[NewspaperEditionResponse]:
        """Loads a persisted newspaper edition snapshot from the database."""
        stmt = (
            select(NewspaperEdition)
            .where(
                NewspaperEdition.user_id == user_id,
                NewspaperEdition.edition_date == edition_date,
            )
            .options(
                selectinload(NewspaperEdition.stories).selectinload(
                    NewspaperStory.article
                ).selectinload(Article.topics),
                selectinload(NewspaperEdition.stories).selectinload(
                    NewspaperStory.article
                ).selectinload(Article.analysis),
                selectinload(NewspaperEdition.stories).selectinload(
                    NewspaperStory.article
                ).selectinload(Article.source),
            )
        )
        result = await self.session.execute(stmt)
        edition = result.scalar_one_or_none()
        if not edition:
            return None

        return await self._format_edition_response(edition, user_id)

    async def generate_daily_edition(
        self,
        user: Any = None,
        edition_date: Optional[str] = None,
        force_regenerate: bool = False,
        target_date: Optional[str] = None,
        user_id: Any = None,
    ) -> NewspaperEditionResponse:
        """Generates and persists a coherent, structured daily edition."""
        target_date_str = (
            edition_date or target_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        )
        resolved_user = user if user is not None else user_id
        if hasattr(resolved_user, "id"):
            target_user_id = resolved_user.id
        elif isinstance(resolved_user, uuid.UUID):
            target_user_id = resolved_user
        elif isinstance(resolved_user, str):
            target_user_id = uuid.UUID(resolved_user)
        else:
            raise ValueError("Valid user or user_id required for newspaper generation.")

        user_id = target_user_id

        # Check existing edition
        stmt = select(NewspaperEdition).where(
            NewspaperEdition.user_id == user_id,
            NewspaperEdition.edition_date == target_date_str,
        )
        existing_result = await self.session.execute(stmt)
        existing_edition = existing_result.scalar_one_or_none()

        if existing_edition and not force_regenerate:
            return await self._format_edition_response(existing_edition, user_id)

        # 1. Candidate selection & personal relevance
        target_dt = datetime.strptime(target_date_str, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
        candidates = await self.candidate_selector.get_candidate_articles(
            user_id=user_id,
            target_date=target_dt,
        )

        # 2. Cluster similar stories to prevent multi-source duplicates
        clustered_candidates, cluster_map = await self.story_clusterer.cluster_and_elect_primary(
            candidates
        )

        # 3. Editorial scoring
        profile = await self.candidate_selector.personalization_service.get_user_interest_profile(
            user_id
        )
        scored_candidates = self.editorial_scorer.score_candidates(
            clustered_candidates,
            cluster_map=cluster_map,
            now=target_dt,
        )

        # 4. Lead story selection
        lead_candidate, remaining_candidates = self.lead_selector.select_lead(
            scored_candidates
        )

        # 5. Topic & entity diversity filtering
        top_interests = list(profile.topic_names_map.values())
        diversified_remaining = self.diversity_filter.apply_diversity(
            remaining_candidates,
            user_top_interests=top_interests,
        )

        # If lead exists, attach its explanation too
        if lead_candidate:
            lead_candidate.personal_explanation = (
                self.diversity_filter._generate_explanation(
                    lead_candidate, [t.lower() for t in top_interests]
                )
            )

        # 6. Section assignment & layout hierarchy
        assigned_stories = self.section_builder.assign_layouts_and_sections(
            lead_story=lead_candidate,
            remaining_stories=diversified_remaining,
        )

        # 7. Subtitle construction
        subtitle = self._generate_personalized_subtitle(top_interests)

        # 8. Persist edition transactionally
        if existing_edition:
            # Delete old stories
            await self.session.execute(
                delete(NewspaperStory).where(
                    NewspaperStory.edition_id == existing_edition.id
                )
            )
            edition_model = existing_edition
            edition_model.title = settings.NEWSPAPER_DEFAULT_MASTHEAD
            edition_model.subtitle = subtitle
            edition_model.status = "READY"
            edition_model.generated_at = datetime.now(timezone.utc)
        else:
            edition_model = NewspaperEdition(
                user_id=user_id,
                edition_date=target_date_str,
                title=settings.NEWSPAPER_DEFAULT_MASTHEAD,
                subtitle=subtitle,
                status="READY",
                generated_at=datetime.now(timezone.utc),
            )
            self.session.add(edition_model)
            await self.session.flush()

        # Add story placements
        for item in assigned_stories:
            cand_story = item["story"]
            art = cand_story.scored_article.article
            story_model = NewspaperStory(
                edition_id=edition_model.id,
                article_id=art.id,
                section=item["section"],
                position=item["position"],
                layout_type=item["layout_type"],
                editorial_score=cand_story.editorial_score,
                is_lead=item["is_lead"],
                personalization_reason=cand_story.personal_explanation,
                display_headline=art.title,  # Store publisher headline
            )
            self.session.add(story_model)

        await self.session.commit()

        # 9. Return structured response
        return await self.get_edition_by_date(user_id, target_date_str)

    def _generate_personalized_subtitle(self, top_interests: List[str]) -> str:
        """Creates a subtle, personalized masthead subtitle without exposing private stats."""
        if not top_interests:
            return "Your curated daily briefing from trusted sources across the globe."
        
        sample = top_interests[:3]
        if len(sample) == 1:
            return f"Your morning edition, curated with a focus on {sample[0]}."
        elif len(sample) == 2:
            return f"Your morning edition, focused on {sample[0]} and {sample[1]}."
        else:
            return f"Your morning edition, focused on {sample[0]}, {sample[1]}, and {sample[2]}."

    async def _format_edition_response(
        self, edition: NewspaperEdition, user_id: uuid.UUID
    ) -> NewspaperEditionResponse:
        """Maps persistent models into the structured NewspaperEditionResponse."""
        # Query user actions for articles in this edition
        article_ids = [s.article_id for s in edition.stories]
        actions_map = await self.action_repo.get_user_actions_map(user_id, article_ids)

        # Query Story Intelligence models for these articles
        from app.story_intelligence.models import StoryArticle, Story
        stmt_story_art = (
            select(StoryArticle, Story)
            .join(Story, Story.id == StoryArticle.story_id)
            .where(StoryArticle.article_id.in_(article_ids))
        )
        res_sa = await self.session.execute(stmt_story_art)
        story_info_map = {}
        for sa, story_obj in res_sa.all():
            story_info_map[sa.article_id] = {
                "story_id": story_obj.id,
                "story_slug": story_obj.slug,
                "story_article_count": story_obj.article_count,
                "story_source_count": story_obj.source_count,
            }

        # Build story responses
        story_responses: List[NewspaperStoryResponse] = []
        sections_dict: Dict[str, List[NewspaperStoryResponse]] = {}
        lead_story_response: Optional[NewspaperStoryResponse] = None

        for s in edition.stories:
            art = s.article
            acts = actions_map.get(art.id, set())
            if "NOT_INTERESTED" in acts or "DISLIKED" in acts:
                continue

            topics_list = [
                t.name if hasattr(t, "name") else str(t)
                for t in (art.topics or [])
            ]
            
            st_info = story_info_map.get(art.id, {})
            sr = NewspaperStoryResponse(
                id=s.id,
                article_id=s.article_id,
                title=s.display_headline or art.title,
                original_headline=art.title,
                summary=art.summary or art.description,
                content=art.content,
                url=art.canonical_url or art.source_url,
                top_image_url=art.image_url,
                author=art.author,
                source_name=art.source.name if art.source else "Independent Source",
                published_at=art.published_at,
                section=s.section,
                position=s.position,
                layout_type=s.layout_type,
                editorial_score=s.editorial_score,
                is_lead=s.is_lead,
                personalization_reason=s.personalization_reason,
                primary_category=art.primary_category,
                topics=topics_list,
                reading_time_minutes=art.reading_time_minutes or 3,
                is_saved="SAVED" in acts,
                is_liked="LIKED" in acts,
                is_read="READ" in acts,
                relevance_score=s.editorial_score,
                status="PUBLISHED",
                story_id=st_info.get("story_id"),
                story_slug=st_info.get("story_slug"),
                story_article_count=st_info.get("story_article_count", 1),
                story_source_count=st_info.get("story_source_count", 1),
            )
            story_responses.append(sr)


            if s.is_lead and not lead_story_response:
                lead_story_response = sr

            if s.section not in sections_dict:
                sections_dict[s.section] = []
            sections_dict[s.section].append(sr)

        # Fallback lead if lead was filtered out
        if not lead_story_response and story_responses:
            lead_story_response = story_responses[0]

        # Format ordered sections (omit empty sections)
        section_order = [
            ControlledSection.TOP_STORIES.value,
            ControlledSection.TECHNOLOGY.value,
            ControlledSection.SCIENCE.value,
            ControlledSection.BUSINESS.value,
            ControlledSection.WORLD.value,
            ControlledSection.HEALTH.value,
            ControlledSection.SPORTS.value,
            ControlledSection.ENTERTAINMENT.value,
            ControlledSection.OTHER.value,
        ]

        formatted_sections: List[NewspaperSectionResponse] = []
        for sec_name in section_order:
            if sec_name in sections_dict and sections_dict[sec_name]:
                formatted_sections.append(
                    NewspaperSectionResponse(
                        name=sec_name,
                        display_name=sec_name.title(),
                        stories=sections_dict[sec_name],
                        articles=sections_dict[sec_name],
                        story_count=len(sections_dict[sec_name]),
                        topic={
                            "id": str(uuid.uuid4()),
                            "name": sec_name.title(),
                            "slug": sec_name.lower().replace(" ", "-"),
                        },
                    )
                )

        # Add any other unexpected sections
        for sec_name, stories in sections_dict.items():
            if sec_name not in section_order and stories:
                formatted_sections.append(
                    NewspaperSectionResponse(
                        name=sec_name,
                        display_name=sec_name.title(),
                        stories=stories,
                        articles=stories,
                        story_count=len(stories),
                        topic={
                            "id": str(uuid.uuid4()),
                            "name": sec_name.title(),
                            "slug": sec_name.lower().replace(" ", "-"),
                        },
                    )
                )

        profile = await self.candidate_selector.personalization_service.get_user_interest_profile(
            user_id
        )
        top_interests = list(profile.topic_names_map.values())
        if top_interests:
            curation_summary = f"Curated edition focused on {', '.join(top_interests)}"
        else:
            curation_summary = f"Curated edition for {edition.edition_date}"

        edition_info = {
            "date": edition.edition_date,
            "title": edition.title,
            "subtitle": edition.subtitle,
        }

        # Query user for backwards compatibility
        user_stmt = select(User).where(User.id == user_id)
        user_res = await self.session.execute(user_stmt)
        user_obj = user_res.scalar_one_or_none()
        user_info = {
            "id": str(user_id),
            "name": (user_obj.full_name or user_obj.email) if user_obj else "Reader",
            "email": user_obj.email if user_obj else "",
        }

        gen_at = edition.generated_at
        if gen_at and gen_at.tzinfo is None:
            gen_at = gen_at.replace(tzinfo=timezone.utc)

        return NewspaperEditionResponse(
            id=edition.id,
            user_id=edition.user_id,
            edition_date=edition.edition_date,
            title=edition.title,
            subtitle=edition.subtitle,
            status=edition.status,
            generated_at=gen_at,
            curation_summary=curation_summary,
            has_interests=profile.has_interests,
            lead_story=lead_story_response,
            featured_article=lead_story_response,
            edition=edition_info,
            user=user_info,
            sections=formatted_sections,
            total_stories=len(story_responses),
        )
