"""editor.py — Phase 17 Editorial Newsroom Main Service."""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.user import User, UserProfile
from app.models.article import Article
from app.models.topic import Topic
from app.models.interest import UserInterest
from app.models.action import UserArticleAction
from app.models.reading_history import ReadingHistory
from app.newspaper.models import (
    NewspaperEdition,
    NewspaperSection,
    NewspaperStory,
)
from app.newspaper.schemas import (
    NewspaperEditionResponse,
    NewspaperSectionResponse,
    NewspaperStoryResponse,
    StoryLayoutType,
)
from app.editorial.schemas import (
    EditionStatus,
    EditionStatusResponse,
    EditionVersionSummary,
    EditorialCandidate,
    EditorialDebugResponse,
    EditorialDecision,
    EditorialRole,
    EditorialWeights,
    SectionType,
)
from app.editorial.candidate_selector import EditorialCandidateSelector
from app.editorial.composer import EditorialComposer

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensures datetime is timezone-aware UTC, even if returned naive from SQLite."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class EditorialNewsroom:
    """
    Main Service for the Personalized Editorial Newspaper Engine.
    Behaves like a personal news editor composing bespoke daily newspaper editions.
    """

    def __init__(self, session: AsyncSession, weights: Optional[EditorialWeights] = None):
        self.session = session
        self.weights = weights or EditorialWeights()
        self.candidate_selector = EditorialCandidateSelector(session)
        self.composer = EditorialComposer(self.weights)

    def get_user_today_date_str(self, user: Optional[User]) -> str:
        """Determines the current local YYYY-MM-DD date in the user's configured timezone."""
        user_tz_name = settings.DEFAULT_TIMEZONE
        if user:
            try:
                from sqlalchemy import inspect as sa_inspect
                insp = sa_inspect(user, raise_errors=False)
                if insp and "profile" in insp.attrs:
                    profile = insp.attrs["profile"].loaded_value
                    if profile and hasattr(profile, "timezone") and profile.timezone:
                        user_tz_name = profile.timezone
            except Exception:
                pass

        try:
            tz = ZoneInfo(user_tz_name)
            local_dt = datetime.now(tz)
            return local_dt.strftime("%Y-%m-%d")
        except Exception:
            return utc_now().strftime("%Y-%m-%d")

    async def generate_edition(
        self,
        user_id: uuid.UUID,
        edition_date: Optional[str] = None,
        force_refresh: bool = False,
        version: Optional[int] = None,
    ) -> NewspaperEditionResponse:
        """
        Generates or refreshes a personalized newspaper edition for user and date.
        If force_refresh is True or edition is stale, increments version number and saves new snapshot.
        Gracefully handles failures with previous edition or emergency fallback.
        """
        stmt = (
            select(User)
            .options(selectinload(User.profile), selectinload(User.interests))
            .where(User.id == user_id)
        )
        res = await self.session.execute(stmt)
        user = res.scalars().first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        target_date_str = edition_date or self.get_user_today_date_str(user)

        # Check existing editions for this date
        latest_edition = await self._get_latest_edition_model(user_id, target_date_str)

        # If already exists and no refresh requested, return stored snapshot
        if latest_edition and not force_refresh and latest_edition.status == EditionStatus.READY.value:
            return await self._format_edition_response(latest_edition, user)

        # Determine next version
        next_version = (latest_edition.version + 1) if (latest_edition and force_refresh) else (version or 1)

        try:
            # 1. Collect candidates
            candidates, exclusions = await self.candidate_selector.get_candidate_pool(
                user_id=user_id
            )

            # Extract user top topic names for contextual explanations
            user_topics: List[str] = []
            if user.interests:
                stmt = select(Topic).where(Topic.id.in_([i.topic_id for i in user.interests if i.preference_type == "POSITIVE"]))
                t_res = await self.session.execute(stmt)
                user_topics = [t.name for t in t_res.scalars().all()]

            # 2. Compose edition
            lead_story, sections_map, section_metadata, editorial_summary, debug_decisions = self.composer.compose_edition(
                candidates=candidates,
                user_top_topics=user_topics,
            )

            # 3. Create persistent NewspaperEdition
            subtitle = f"Morning Edition (v{next_version})" if next_version == 1 else f"Updated Edition (v{next_version})"
            edition = NewspaperEdition(
                user_id=user_id,
                edition_date=target_date_str,
                title="PERSONAL DAILY",
                subtitle=subtitle,
                editorial_summary=editorial_summary,
                status=EditionStatus.READY.value,
                version=next_version,
                generated_at=utc_now(),
            )
            self.session.add(edition)
            await self.session.flush()

            # 4. Create NewspaperSection and NewspaperStory records
            story_position = 0

            for sec_type, sec_title, disp_order in section_metadata:
                section_model = NewspaperSection(
                    edition_id=edition.id,
                    section_type=sec_type,
                    display_order=disp_order,
                    title=sec_title,
                )
                self.session.add(section_model)
                await self.session.flush()

                sec_candidates = sections_map.get(sec_type, [])
                for cand in sec_candidates:
                    is_lead = (cand.editorial_role == EditorialRole.LEAD.value or sec_type == SectionType.LEAD.value)
                    layout = (
                        StoryLayoutType.LEAD.value if is_lead
                        else (
                            StoryLayoutType.FEATURE.value if cand.editorial_role == EditorialRole.TOP_STORY.value
                            else (StoryLayoutType.COMPACT.value if cand.editorial_role == EditorialRole.BRIEF.value else StoryLayoutType.STANDARD.value)
                        )
                    )

                    story_model = NewspaperStory(
                        edition_id=edition.id,
                        section_id=section_model.id,
                        story_id=cand.story_id,
                        article_id=cand.article_id,
                        position=story_position,
                        editorial_role=cand.editorial_role,
                        editorial_score=cand.editorial_score,
                        reason=cand.reason,
                        section=sec_type.replace("_", " "),
                        layout_type=layout,
                        is_lead=is_lead,
                        personalization_reason=cand.reason,
                        display_headline=cand.title,
                    )
                    self.session.add(story_model)
                    story_position += 1

            await self.session.commit()
            fresh_edition = await self._get_latest_edition_model(user_id, target_date_str)
            if fresh_edition:
                return await self._format_edition_response(fresh_edition, user_id)
            return await self._format_edition_response(edition, user_id)

        except Exception as e:
            logger.error(f"Editorial generation failed for user {user_id} on {target_date_str}: {e}", exc_info=True)
            await self.session.rollback()

            # Fallback 1: Return previous valid edition
            if latest_edition and latest_edition.status == EditionStatus.READY.value:
                logger.info(f"Returning previous valid edition {latest_edition.id} due to generation error.")
                return await self._format_edition_response(latest_edition, user_id)

            # Fallback 2: Generate emergency minimal fallback edition
            return await self._generate_emergency_fallback(user_id, target_date_str, next_version)

    async def get_today_edition(self, user: User) -> NewspaperEditionResponse:
        """Retrieves or creates today's edition for the given user."""
        today_str = self.get_user_today_date_str(user)
        latest = await self._get_latest_edition_model(user.id, today_str)
        if latest and latest.status == EditionStatus.READY.value:
            return await self._format_edition_response(latest, user)
        return await self.generate_edition(user_id=user.id, edition_date=today_str)

    async def get_edition_by_date(
        self,
        user_id: uuid.UUID,
        edition_date: str,
        version: Optional[int] = None,
    ) -> Optional[NewspaperEditionResponse]:
        """Retrieves a historical edition snapshot by date and optional version."""
        stmt = select(User).options(selectinload(User.profile)).where(User.id == user_id)
        res = await self.session.execute(stmt)
        user = res.scalars().first()
        if not user:
            return None

        if version is not None:
            stmt = (
                select(NewspaperEdition)
                .options(
                    selectinload(NewspaperEdition.sections).selectinload(NewspaperSection.stories).selectinload(NewspaperStory.article),
                    selectinload(NewspaperEdition.sections).selectinload(NewspaperSection.stories).selectinload(NewspaperStory.story),
                    selectinload(NewspaperEdition.stories).selectinload(NewspaperStory.article),
                    selectinload(NewspaperEdition.stories).selectinload(NewspaperStory.story),
                )
                .where(
                    NewspaperEdition.user_id == user_id,
                    NewspaperEdition.edition_date == edition_date,
                    NewspaperEdition.version == version,
                )
            )
            res = await self.session.execute(stmt)
            edition = res.scalars().first()
        else:
            edition = await self._get_latest_edition_model(user_id, edition_date)

        if not edition:
            return None
        return await self._format_edition_response(edition, user)

    async def get_edition_versions(
        self, user_id: uuid.UUID, edition_date: str
    ) -> List[EditionVersionSummary]:
        """Returns list of version summaries for a specific date."""
        stmt = (
            select(NewspaperEdition)
            .options(
                selectinload(NewspaperEdition.stories).selectinload(NewspaperStory.article)
            )
            .where(
                NewspaperEdition.user_id == user_id,
                NewspaperEdition.edition_date == edition_date,
            )
            .order_by(NewspaperEdition.version.desc())
        )
        res = await self.session.execute(stmt)
        editions = list(res.scalars().all())

        summaries: List[EditionVersionSummary] = []
        for ed in editions:
            lead_title = None
            for s in ed.stories:
                if s.is_lead or s.editorial_role == EditorialRole.LEAD.value:
                    lead_title = s.article.title if s.article else s.display_headline
                    break

            summaries.append(
                EditionVersionSummary(
                    id=ed.id,
                    version=ed.version,
                    edition_date=ed.edition_date,
                    status=ed.status,
                    generated_at=ed.generated_at,
                    total_stories=len(ed.stories),
                    lead_title=lead_title,
                    editorial_summary=ed.editorial_summary,
                )
            )
        return summaries

    async def get_edition_status(
        self, user_id: uuid.UUID, edition_date: str
    ) -> EditionStatusResponse:
        """Checks status and staleness of an edition."""
        edition = await self._get_latest_edition_model(user_id, edition_date)
        if not edition:
            return EditionStatusResponse(
                edition_date=edition_date,
                version=0,
                status="NOT_GENERATED",
                generated_at=None,
                is_stale=False,
                stale_reasons=["No edition generated yet"],
            )

        is_stale, reasons = await self._check_if_stale(edition)
        return EditionStatusResponse(
            edition_date=edition.edition_date,
            version=edition.version,
            status=edition.status if not is_stale else EditionStatus.STALE.value,
            generated_at=edition.generated_at,
            is_stale=is_stale,
            stale_reasons=reasons,
        )

    async def get_editorial_debug(
        self, user_id: uuid.UUID, edition_date: str
    ) -> EditorialDebugResponse:
        """Generates detailed editorial audit and debug information for inspection."""
        user = await self.session.get(User, user_id, options=[selectinload(User.interests)])
        if not user:
            raise ValueError(f"User {user_id} not found")

        candidates, exclusions = await self.candidate_selector.get_candidate_pool(user_id=user_id)
        user_topics = [i.topic_id for i in user.interests if i.preference_type == "POSITIVE"]

        lead_story, sections_map, section_metadata, summary, decisions = self.composer.compose_edition(
            candidates=candidates,
            user_top_topics=[],
        )

        selected_decisions = [d for d in decisions if d.decision == "SELECTED"]
        excluded_decisions = [d for d in decisions if d.decision == "EXCLUDED"]

        # Add explicit candidate exclusion reasons from candidate_selector
        for ex in exclusions:
            excluded_decisions.append(
                EditorialDecision(
                    item_id=ex.get("item_id", ""),
                    title=ex.get("title", ""),
                    editorial_score=0.0,
                    role="NONE",
                    section="NONE",
                    decision="EXCLUDED",
                    reason=ex.get("reason", "Filtered"),
                    factors={},
                )
            )

        section_counts = {sec_type: len(stories) for sec_type, stories in sections_map.items()}

        lead_info = None
        if lead_story:
            lead_info = {
                "article_id": str(lead_story.article_id),
                "title": lead_story.title,
                "editorial_score": lead_story.editorial_score,
                "reason": lead_story.reason,
            }

        return EditorialDebugResponse(
            user_id=user_id,
            edition_date=edition_date,
            version=1,
            candidate_count=len(candidates) + len(exclusions),
            selected_count=len(selected_decisions),
            excluded_count=len(excluded_decisions),
            lead_selection=lead_info,
            section_assignments=section_counts,
            diversity_decisions={"total_sections": len(sections_map)},
            selected_stories=selected_decisions,
            excluded_stories=excluded_decisions,
        )

    async def _get_latest_edition_model(
        self, user_id: uuid.UUID, edition_date: str
    ) -> Optional[NewspaperEdition]:
        stmt = (
            select(NewspaperEdition)
            .options(
                selectinload(NewspaperEdition.sections).selectinload(NewspaperSection.stories).selectinload(NewspaperStory.article).selectinload(Article.analysis),
                selectinload(NewspaperEdition.sections).selectinload(NewspaperSection.stories).selectinload(NewspaperStory.article).selectinload(Article.topics),
                selectinload(NewspaperEdition.sections).selectinload(NewspaperSection.stories).selectinload(NewspaperStory.article).selectinload(Article.source),
                selectinload(NewspaperEdition.sections).selectinload(NewspaperSection.stories).selectinload(NewspaperStory.story),
                selectinload(NewspaperEdition.stories).selectinload(NewspaperStory.article).selectinload(Article.analysis),
                selectinload(NewspaperEdition.stories).selectinload(NewspaperStory.article).selectinload(Article.topics),
                selectinload(NewspaperEdition.stories).selectinload(NewspaperStory.article).selectinload(Article.source),
                selectinload(NewspaperEdition.stories).selectinload(NewspaperStory.story),
            )
            .where(
                NewspaperEdition.user_id == user_id,
                NewspaperEdition.edition_date == edition_date,
            )
            .order_by(NewspaperEdition.version.desc())
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def _check_if_stale(self, edition: NewspaperEdition) -> Tuple[bool, List[str]]:
        reasons: List[str] = []
        gen_at = ensure_utc(edition.generated_at) or utc_now()
        age_hours = (utc_now() - gen_at).total_seconds() / 3600.0

        if age_hours > 6.0:
            reasons.append("Edition is older than 6 hours")

        return (len(reasons) > 0, reasons)

    async def _format_edition_response(
        self, edition: NewspaperEdition, user: Optional[Any] = None
    ) -> NewspaperEditionResponse:
        # Resolve target user_id safely
        target_user_id = user.id if (user is not None and hasattr(user, "id")) else edition.user_id

        # Query all stories for this edition with eager loading to avoid any lazy loading / greenlet issues
        st_stmt = (
            select(NewspaperStory)
            .options(
                selectinload(NewspaperStory.article).selectinload(Article.analysis),
                selectinload(NewspaperStory.article).selectinload(Article.topics),
                selectinload(NewspaperStory.article).selectinload(Article.source),
                selectinload(NewspaperStory.story),
            )
            .where(NewspaperStory.edition_id == edition.id)
            .order_by(NewspaperStory.position.asc())
        )
        st_res = await self.session.execute(st_stmt)
        edition_stories = list(st_res.scalars().all())

        # Query all sections for this edition
        sec_stmt = (
            select(NewspaperSection)
            .where(NewspaperSection.edition_id == edition.id)
            .order_by(NewspaperSection.display_order.asc())
        )
        sec_res = await self.session.execute(sec_stmt)
        edition_sections = list(sec_res.scalars().all())

        # Fetch user action states for articles in this edition
        article_ids = [s.article_id for s in edition_stories if s.article_id]
        saved_ids: set = set()
        liked_ids: set = set()
        not_interested_ids: set = set()
        read_ids: set = set()

        if article_ids:
            act_stmt = select(UserArticleAction).where(
                UserArticleAction.user_id == target_user_id,
                UserArticleAction.article_id.in_(article_ids),
            )
            act_res = await self.session.execute(act_stmt)
            for act in act_res.scalars().all():
                act_val = getattr(act, "action", getattr(act, "action_type", ""))
                if act_val == "SAVE":
                    saved_ids.add(act.article_id)
                elif act_val == "LIKE":
                    liked_ids.add(act.article_id)
                elif act_val == "NOT_INTERESTED":
                    not_interested_ids.add(act.article_id)

            read_stmt = select(ReadingHistory.article_id).where(
                ReadingHistory.user_id == target_user_id,
                ReadingHistory.article_id.in_(article_ids),
                ReadingHistory.last_completion_percentage >= 0.8,
            )
            read_res = await self.session.execute(read_stmt)
            read_ids = set(read_res.scalars().all())

        # Check user interests
        int_stmt = select(func.count(UserInterest.id)).where(
            UserInterest.user_id == target_user_id,
            UserInterest.preference_type == "POSITIVE",
        )
        int_count = (await self.session.execute(int_stmt)).scalar() or 0
        has_user_interests = int_count > 0

        # Build story responses
        lead_story_resp: Optional[NewspaperStoryResponse] = None
        sections_dict: Dict[str, List[NewspaperStoryResponse]] = {}
        section_titles: Dict[str, str] = {}

        if edition_sections:
            stories_by_section_id: Dict[uuid.UUID, List[NewspaperStory]] = {}
            for st in edition_stories:
                if st.section_id:
                    stories_by_section_id.setdefault(st.section_id, []).append(st)

            for sec in edition_sections:
                section_titles[sec.section_type] = sec.title
                sec_stories: List[NewspaperStoryResponse] = []
                for st in stories_by_section_id.get(sec.id, []):
                    if st.article_id and st.article_id in not_interested_ids:
                        continue
                    st_resp = self._build_story_response(
                        st, saved_ids, liked_ids, not_interested_ids, read_ids
                    )
                    sec_stories.append(st_resp)
                    if st.is_lead or st.editorial_role == EditorialRole.LEAD.value:
                        if not lead_story_resp and (st.article_id not in not_interested_ids):
                            lead_story_resp = st_resp
                if sec_stories:
                    sections_dict[sec.section_type] = sec_stories
        else:
            for st in edition_stories:
                if st.article_id and st.article_id in not_interested_ids:
                    continue
                st_resp = self._build_story_response(
                    st, saved_ids, liked_ids, not_interested_ids, read_ids
                )
                sec_key = st.section or "TOP STORIES"
                sections_dict.setdefault(sec_key, []).append(st_resp)
                if st.is_lead or st.editorial_role == EditorialRole.LEAD.value:
                    if not lead_story_resp and (st.article_id not in not_interested_ids):
                        lead_story_resp = st_resp

        # Format sections list
        section_responses: List[NewspaperSectionResponse] = []
        for sec_type, stories_list in sections_dict.items():
            if sec_type == SectionType.LEAD.value:
                continue
            disp_name = section_titles.get(sec_type, sec_type.replace("_", " ").title())
            topic_info = {
                "id": str(uuid.uuid4()),
                "name": disp_name,
                "slug": sec_type.lower().replace("_", "-"),
            }
            section_responses.append(
                NewspaperSectionResponse(
                    name=sec_type,
                    display_name=disp_name,
                    story_count=len(stories_list),
                    stories=stories_list,
                    articles=stories_list,
                    topic=topic_info,
                )
            )

        # Curation summary with interests
        summary_text = edition.editorial_summary or "Your personalized edition is ready."
        if has_user_interests:
            top_topics_stmt = (
                select(Topic.name)
                .join(UserInterest, UserInterest.topic_id == Topic.id)
                .where(
                    UserInterest.user_id == target_user_id,
                    UserInterest.preference_type == "POSITIVE",
                )
            )
            top_topic_names = list((await self.session.execute(top_topics_stmt)).scalars().all())
            if top_topic_names:
                summary_text = f"Curated for your interests in {', '.join(top_topic_names)}. " + summary_text

        # User summary info
        u_stmt = select(User).where(User.id == target_user_id)
        target_user_obj = (await self.session.execute(u_stmt)).scalars().first()
        user_summary = {
            "id": target_user_id,
            "name": target_user_obj.full_name if (target_user_obj and target_user_obj.full_name) else "Reader",
            "email": target_user_obj.email if target_user_obj else "reader@example.com",
        }
        edition_info = {
            "date": edition.edition_date,
            "title": edition.title,
            "subtitle": edition.subtitle,
        }
        featured_article = None
        if lead_story_resp and lead_story_resp.article_id not in not_interested_ids:
            featured_article = lead_story_resp.model_dump()
            featured_article["relevance_score"] = 0.95

        return NewspaperEditionResponse(
            id=edition.id,
            user_id=edition.user_id,
            edition_date=edition.edition_date,
            title=edition.title,
            subtitle=edition.subtitle,
            status=edition.status,
            generated_at=edition.generated_at,
            curation_summary=summary_text,
            has_interests=has_user_interests,
            lead_story=lead_story_resp,
            featured_article=featured_article,
            edition=edition_info,
            user=user_summary,
            sections=section_responses,
            total_stories=len(edition_stories),
        )

    def _build_story_response(
        self,
        st: NewspaperStory,
        saved_ids: set,
        liked_ids: set,
        not_interested_ids: set,
        read_ids: set,
    ) -> NewspaperStoryResponse:
        art = st.article
        topics = [t.name for t in art.topics] if (art and art.topics) else []
        analysis = art.analysis if art else None

        return NewspaperStoryResponse(
            id=st.id,
            article_id=st.article_id or (art.id if art else uuid.uuid4()),
            title=st.display_headline or (art.title if art else "Editorial Item"),
            original_headline=art.title if art else st.display_headline,
            summary=(analysis.summary if analysis else art.description) if art else None,
            content=art.content if art else None,
            url=(art.canonical_url or art.source_url) if art else None,
            top_image_url=art.image_url if art else None,
            author=art.author if art else None,
            source_name=(art.source.name if (art and art.source) else "News Desk"),
            published_at=art.published_at if art else st.created_at,
            reading_time_minutes=art.reading_time_minutes if art else 3,
            is_full_text_available=art.is_full_text_available if art else True,
            primary_category=analysis.primary_category if analysis else (st.section or "GENERAL"),
            topics=topics,
            section=st.section or "TOP STORIES",
            position=st.position,
            layout_type=st.layout_type or StoryLayoutType.STANDARD.value,
            editorial_score=st.editorial_score,
            is_lead=st.is_lead,
            personalization_reason=st.reason or st.personalization_reason,
            display_headline=st.display_headline or (art.title if art else None),
            status="PUBLISHED",
            is_saved=(st.article_id in saved_ids),
            is_liked=(st.article_id in liked_ids),
            is_read=(st.article_id in read_ids),
            is_not_interested=(st.article_id in not_interested_ids),
            story_id=st.story_id,
            story_slug=st.story.slug if st.story else None,
            story_article_count=st.story.article_count if st.story else 1,
            story_source_count=st.story.source_count if st.story else 1,
        )

    async def _generate_emergency_fallback(
        self, user_id: uuid.UUID, target_date_str: str, version: int
    ) -> NewspaperEditionResponse:
        """Creates a graceful fallback edition if advanced components encounter an unexpected error."""
        logger.warning(f"Generating emergency fallback edition for user {user_id}")
        stmt = (
            select(Article)
            .options(selectinload(Article.analysis), selectinload(Article.topics), selectinload(Article.source))
            .where(Article.status == "PUBLISHED")
            .order_by(Article.published_at.desc())
            .limit(10)
        )
        res = await self.session.execute(stmt)
        articles = list(res.scalars().all())

        edition = NewspaperEdition(
            user_id=user_id,
            edition_date=target_date_str,
            title="PERSONAL DAILY",
            subtitle=f"Daily Edition (v{version})",
            editorial_summary="Today's essential news edition.",
            status=EditionStatus.READY.value,
            version=version,
            generated_at=utc_now(),
        )
        self.session.add(edition)
        await self.session.flush()

        sec = NewspaperSection(
            edition_id=edition.id,
            section_type=SectionType.TOP_STORIES.value,
            display_order=1,
            title="Top Stories",
        )
        self.session.add(sec)
        await self.session.flush()

        for idx, art in enumerate(articles):
            is_lead = (idx == 0)
            story = NewspaperStory(
                edition_id=edition.id,
                section_id=sec.id,
                article_id=art.id,
                position=idx,
                editorial_role=EditorialRole.LEAD.value if is_lead else EditorialRole.STANDARD.value,
                editorial_score=0.8 if is_lead else 0.5,
                reason="Top general story." if is_lead else "Standard news item.",
                section="TOP STORIES",
                layout_type=StoryLayoutType.LEAD.value if is_lead else StoryLayoutType.STANDARD.value,
                is_lead=is_lead,
                display_headline=art.title,
            )
            self.session.add(story)

        await self.session.commit()
        fresh_edition = await self._get_latest_edition_model(user_id, target_date_str)
        if fresh_edition:
            return await self._format_edition_response(fresh_edition, user_id)
        return await self._format_edition_response(edition, user_id)
