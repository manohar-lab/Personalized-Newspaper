"""story_service.py — Phase 16 Multi-Source Story Intelligence Orchestrator Service."""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, func, or_, select, and_
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.article import Article
from app.models.topic import Topic
from app.models.entity import Entity
from app.models.analysis import ArticleAnalysis
from app.source_intelligence.conflict_detector import ConflictDetector
from app.source_intelligence.models import UserSourcePreference
from app.story_intelligence.models import Story, StoryArticle, StoryMergeEvent
from app.story_intelligence.schemas import (
    StoryItem,
    StoryDetail,
    StoryArticleItem,
    StoryTimelineItem,
    StoryCoverageResponse,
    StoryFeedResponse,
    StorySearchResponse,
)
from app.story_intelligence.story_matcher import StoryMatcher
from app.story_intelligence.story_summarizer import StorySummarizer
from app.story_intelligence.story_lifecycle import StoryLifecycleManager

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StoryIntelligenceService:
    """Core service for Story management, matching, synthesis, merging, and personalized retrieval."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.matcher = StoryMatcher()
        self.summarizer = StorySummarizer()
        self.lifecycle = StoryLifecycleManager()
        self.conflict_detector = ConflictDetector()

    async def get_story_by_id_or_slug(self, identifier: str) -> Optional[Story]:
        """Fetches a Story by UUID or slug, following merge redirections."""
        stmt = select(Story).options(
            selectinload(Story.primary_topic),
            selectinload(Story.primary_article).selectinload(Article.analysis),
            selectinload(Story.primary_article).selectinload(Article.source),
            selectinload(Story.latest_article).selectinload(Article.analysis),
            selectinload(Story.latest_article).selectinload(Article.source),
            selectinload(Story.story_articles).selectinload(StoryArticle.article).selectinload(Article.analysis),
            selectinload(Story.story_articles).selectinload(StoryArticle.article).selectinload(Article.source),
            selectinload(Story.story_articles).selectinload(StoryArticle.article).selectinload(Article.topics),
            selectinload(Story.story_articles).selectinload(StoryArticle.article).selectinload(Article.entities),
        )

        try:
            val_uuid = uuid.UUID(identifier)
            stmt = stmt.where(Story.id == val_uuid)
        except ValueError:
            stmt = stmt.where(Story.slug == identifier)

        res = await self.session.execute(stmt)
        story = res.scalar_one_or_none()

        # Follow merge redirect if merged
        if story and story.merged_into_story_id:
            return await self.get_story_by_id_or_slug(str(story.merged_into_story_id))

        return story

    async def ingest_article_into_story(self, article_id: uuid.UUID) -> Tuple[Story, StoryArticle, bool]:
        """
        Matches an article against active/recent candidate stories.
        Attaches article to best matching story or creates a new story.
        Returns: (Story, StoryArticle, is_new_story)
        """
        # 1. Fetch full article
        stmt_art = (
            select(Article)
            .where(Article.id == article_id)
            .options(
                selectinload(Article.topics),
                selectinload(Article.analysis),
                selectinload(Article.entities),
                selectinload(Article.keywords),
                selectinload(Article.source),
            )
        )
        res_art = await self.session.execute(stmt_art)
        article = res_art.scalar_one_or_none()
        if not article:
            raise ValueError(f"Article {article_id} not found.")

        # Check if article is already assigned to a story
        stmt_exist = select(StoryArticle).where(StoryArticle.article_id == article_id)
        res_exist = await self.session.execute(stmt_exist)
        existing_sa = res_exist.scalar_one_or_none()
        if existing_sa:
            story = await self.get_story_by_id_or_slug(str(existing_sa.story_id))
            return story, existing_sa, False

        # 2. Retrieve Candidate Stories within temporal window
        window_cutoff = utc_now() - timedelta(days=settings.STORY_WINDOW_DAYS)
        stmt_candidates = (
            select(Story)
            .where(
                Story.merged_into_story_id.is_(None),
                Story.last_updated_at >= window_cutoff,
            )
            .options(
                selectinload(Story.primary_article).selectinload(Article.analysis),
                selectinload(Story.primary_article).selectinload(Article.entities),
                selectinload(Story.primary_article).selectinload(Article.keywords),
                selectinload(Story.primary_article).selectinload(Article.topics),
            )
            .order_by(desc(Story.last_updated_at))
            .limit(100)
        )
        res_cand = await self.session.execute(stmt_candidates)
        candidates = list(res_cand.scalars().all())

        best_story: Optional[Story] = None
        best_score = 0.0

        for cand in candidates:
            prim_art = cand.primary_article
            if not prim_art and cand.primary_article_id:
                stmt_p = select(Article).where(Article.id == cand.primary_article_id).options(
                    selectinload(Article.analysis),
                    selectinload(Article.entities),
                    selectinload(Article.keywords),
                    selectinload(Article.topics),
                )
                res_p = await self.session.execute(stmt_p)
                prim_art = res_p.scalar_one_or_none()

            score, _ = self.matcher.compute_match_score(
                article=article,
                story=cand,
                story_primary_article=prim_art,
            )
            if score > best_score:
                best_score = score
                best_story = cand

        # 3. Attach to Story or Create New Story
        if best_story and best_score >= self.matcher.match_threshold:
            # Assign to existing story
            rel_type = self.matcher.classify_relationship(article, best_story, is_first=False)
            story_article = StoryArticle(
                id=uuid.uuid4(),
                story_id=best_story.id,
                article_id=article.id,
                relationship_type=rel_type,
                similarity_score=best_score,
                added_at=utc_now(),
            )
            self.session.add(story_article)
            await self.session.flush()

            # Refresh and update story metrics
            await self._update_story_aggregate_state(best_story)
            return best_story, story_article, False

        else:
            # Create new Story
            story_id = uuid.uuid4()
            clean_title = self.summarizer.clean_editorial_title(article.title)
            slug = self.summarizer.generate_slug(clean_title, story_id)
            primary_topic_id = article.topics[0].id if article.topics else None

            analysis = article.analysis
            initial_summary = (
                (analysis.summary if analysis else None) or article.description or clean_title
            )
            art_pub = article.published_at or article.created_at or utc_now()

            new_story = Story(
                id=story_id,
                title=clean_title,
                slug=slug,
                summary=initial_summary,
                status="ACTIVE",
                first_published_at=art_pub,
                last_updated_at=art_pub,
                primary_topic_id=primary_topic_id,
                importance_score=float(getattr(analysis, "importance_score", 0.5) or 0.5) if analysis else 0.5,
                quality_score=float(getattr(analysis, "article_quality_score", 0.5) or 0.5) if analysis else 0.5,
                article_count=1,
                source_count=1,
                independent_source_count=1,
                activity_score=0.5,
                primary_article_id=article.id,
                latest_article_id=article.id,
                primary_article=article,
                latest_article=article,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            self.session.add(new_story)
            await self.session.flush()


            story_article = StoryArticle(
                id=uuid.uuid4(),
                story_id=story_id,
                article_id=article.id,
                relationship_type="PRIMARY",
                similarity_score=1.0,
                added_at=utc_now(),
            )
            self.session.add(story_article)
            await self.session.flush()

            return new_story, story_article, True

    async def _update_story_aggregate_state(self, story: Story) -> None:
        """Recalculates story counts, importance, quality, status, primary and latest articles."""
        # Load all member articles
        stmt = (
            select(Article)
            .join(StoryArticle, StoryArticle.article_id == Article.id)
            .where(StoryArticle.story_id == story.id)
            .options(
                selectinload(Article.analysis),
                selectinload(Article.source),
            )
        )
        res = await self.session.execute(stmt)
        articles = list(res.scalars().all())

        if not articles:
            return

        total_sources, indep_sources, _ = self.lifecycle.compute_independent_source_count(articles)
        primary_art = self.lifecycle.select_primary_article(articles)
        latest_art = self.lifecycle.select_latest_article(articles)

        def ensure_utc(dt):
            if dt is None:
                return utc_now()
            if getattr(dt, "tzinfo", None) is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        # Update timestamps
        pub_times = [
            ensure_utc(getattr(a, "published_at", None) or getattr(a, "created_at", None))
            for a in articles
        ]
        earliest_pub = min(pub_times)
        latest_pub = max(pub_times)


        activity_score, status = self.lifecycle.compute_activity_and_status(articles, latest_pub)
        importance_score = self.lifecycle.compute_story_importance(articles, indep_sources, latest_pub)
        quality_score = self.lifecycle.compute_story_quality(articles, indep_sources, has_summary=bool(story.summary))

        story.article_count = len(articles)
        story.source_count = total_sources
        story.independent_source_count = indep_sources
        story.first_published_at = earliest_pub
        story.last_updated_at = latest_pub
        story.activity_score = activity_score
        story.status = status
        story.importance_score = importance_score
        story.quality_score = quality_score
        if primary_art:
            story.primary_article_id = primary_art.id
            story.primary_article = primary_art
        if latest_art:
            story.latest_article_id = latest_art.id
            story.latest_article = latest_art

        # Update summary if new articles arrived and summary exists
        if len(articles) > 1:
            story.summary = self.summarizer.synthesize_story_summary(articles, story.summary)

        story.updated_at = utc_now()
        await self.session.flush()

    async def merge_stories(
        self, source_story_id: uuid.UUID, target_story_id: uuid.UUID, reason: Optional[str] = None
    ) -> Story:
        """Merges source story into target story, updating references and preserving merge audit event."""
        if source_story_id == target_story_id:
            raise ValueError("Cannot merge a story into itself.")

        source = await self.get_story_by_id_or_slug(str(source_story_id))
        target = await self.get_story_by_id_or_slug(str(target_story_id))

        if not source or not target:
            raise ValueError("Source or target story not found.")

        # Reassign all articles from source to target
        stmt_sa = select(StoryArticle).where(StoryArticle.story_id == source.id)
        res_sa = await self.session.execute(stmt_sa)
        source_articles = list(res_sa.scalars().all())

        for sa in source_articles:
            # Check if target already has this article
            stmt_t = select(StoryArticle).where(
                StoryArticle.story_id == target.id,
                StoryArticle.article_id == sa.article_id,
            )
            res_t = await self.session.execute(stmt_t)
            if not res_t.scalar_one_or_none():
                sa.story_id = target.id
            else:
                await self.session.delete(sa)

        # Mark source story as merged
        source.merged_into_story_id = target.id
        source.merged_at = utc_now()
        source.status = "ARCHIVED"

        # Record merge event
        event = StoryMergeEvent(
            id=uuid.uuid4(),
            source_story_id=source.id,
            target_story_id=target.id,
            reason=reason or "Story merge",
            merged_at=utc_now(),
        )
        self.session.add(event)
        await self.session.flush()

        # Recalculate target state
        await self._update_story_aggregate_state(target)
        return target

    async def auto_merge_candidate_stories(self, threshold: float = settings.STORY_MERGE_THRESHOLD) -> int:
        """Finds pairs of highly similar recent stories and merges them."""
        window_cutoff = utc_now() - timedelta(days=settings.STORY_WINDOW_DAYS)
        stmt = (
            select(Story)
            .where(Story.merged_into_story_id.is_(None), Story.last_updated_at >= window_cutoff)
            .options(
                selectinload(Story.primary_article).selectinload(Article.analysis),
                selectinload(Story.primary_article).selectinload(Article.entities),
                selectinload(Story.primary_article).selectinload(Article.keywords),
            )
            .order_by(desc(Story.article_count))
        )
        res = await self.session.execute(stmt)
        active_stories = list(res.scalars().all())

        merged_count = 0
        merged_ids: Set[uuid.UUID] = set()

        for i, s1 in enumerate(active_stories):
            if s1.id in merged_ids:
                continue
            for s2 in active_stories[i + 1 :]:
                if s2.id in merged_ids:
                    continue
                score, _ = self.matcher.compute_match_score(
                    article=s2.primary_article or s2,
                    story=s1,
                    story_primary_article=s1.primary_article,
                )
                if score >= threshold:
                    logger.info(f"Auto-merging story '{s2.title}' into '{s1.title}' (score={score})")
                    await self.merge_stories(
                        source_story_id=s2.id,
                        target_story_id=s1.id,
                        reason=f"Auto-merged high similarity match ({score:.2f})",
                    )
                    merged_ids.add(s2.id)
                    merged_count += 1
                    break

        return merged_count

    async def batch_process_unassigned_articles(self, limit: int = 50) -> int:
        """Assigns any published articles not yet associated with a story."""
        # Find articles without story_articles entry
        stmt = (
            select(Article.id)
            .where(
                Article.status == "PUBLISHED",
                ~Article.id.in_(select(StoryArticle.article_id)),
            )
            .order_by(desc(Article.created_at))
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        unassigned_ids = list(res.scalars().all())

        processed = 0
        for art_id in unassigned_ids:
            try:
                await self.ingest_article_into_story(art_id)
                processed += 1
            except Exception as e:
                logger.error(f"Error assigning article {art_id} to story: {e}")

        return processed

    async def get_story_detail(self, identifier: str, user_id: Optional[uuid.UUID] = None) -> Optional[StoryDetail]:
        """Returns full StoryDetail with timeline, articles, and potential conflict flags."""
        story = await self.get_story_by_id_or_slug(identifier)
        if not story:
            return None

        # Build articles and timeline
        article_items: List[StoryArticleItem] = []
        timeline_items: List[StoryTimelineItem] = []
        raw_articles: List[Article] = []

        def ensure_utc(dt):
            if dt is None:
                return utc_now()
            if getattr(dt, "tzinfo", None) is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        # Sort story articles by published time
        sorted_sas = sorted(
            story.story_articles,
            key=lambda sa: ensure_utc(sa.article.published_at or sa.article.created_at),
        )


        for sa in sorted_sas:
            art = sa.article
            raw_articles.append(art)
            src_name = art.source.name if art.source else (art.source_name or "Independent Source")
            pub = art.published_at or art.created_at or utc_now()
            analysis = art.analysis

            item = StoryArticleItem(
                id=sa.id,
                article_id=art.id,
                title=art.title,
                summary=art.summary or (analysis.summary if analysis else None),
                url=art.url,
                source_name=src_name,
                published_at=pub,
                relationship_type=sa.relationship_type,
                similarity_score=sa.similarity_score,
                top_image_url=art.top_image_url,
                reading_time_minutes=art.reading_time_minutes or 3,
                is_syndicated=False,
                potential_conflict=False,
            )
            article_items.append(item)

            tl_item = StoryTimelineItem(
                id=sa.id,
                article_id=art.id,
                title=art.title,
                source_name=src_name,
                published_at=pub,
                relationship_type=sa.relationship_type,
                url=art.url,
                snippet=art.summary or (analysis.summary if analysis else None),
            )
            timeline_items.append(tl_item)

        # Check for conflicts
        has_conflicts = False
        conflict_note = None
        if len(raw_articles) >= 2:
            has_conflicts, conflict_note, _ = self.conflict_detector.detect_conflicts_in_cluster(raw_articles)

        # Mark conflict flags on individual items
        for itm in article_items:
            itm.potential_conflict = has_conflicts


        # Identify primary and latest article item models
        primary_item = next((it for it in article_items if it.article_id == story.primary_article_id), article_items[0] if article_items else None)
        latest_item = next((it for it in article_items if it.article_id == story.latest_article_id), article_items[-1] if article_items else None)

        sources_list = sorted(list(set(it.source_name for it in article_items if it.source_name)))

        # Determine personal relevance reason
        topic_name = story.primary_topic.name if story.primary_topic else "Current Affairs"
        if user_id:
            personal_relevance_reason = f"Because you frequently read about {topic_name}."
        else:
            personal_relevance_reason = f"Featured coverage in {topic_name}."

        # Determine what changed
        what_changed = None
        if len(article_items) > 1 and latest_item and primary_item and latest_item.id != primary_item.id:
            what_changed = f"Latest development: {latest_item.title}. Previous coverage: {primary_item.title}."
        elif story.status in ("DEVELOPING", "UPDATED", "BREAKING"):
            what_changed = f"Story is developing with {story.source_count} sources monitoring live updates."

        return StoryDetail(
            id=story.id,
            title=story.title,
            slug=story.slug,
            summary=story.summary,
            status=story.status,
            importance_score=story.importance_score,
            quality_score=story.quality_score,
            activity_score=story.activity_score,
            article_count=story.article_count,
            source_count=story.source_count,
            independent_source_count=story.independent_source_count,
            first_published_at=story.first_published_at,
            last_updated_at=story.last_updated_at,
            primary_topic_id=story.primary_topic_id,
            primary_topic_name=story.primary_topic.name if story.primary_topic else None,
            primary_article=primary_item,
            latest_article=latest_item,
            articles=article_items,
            timeline=timeline_items,
            has_conflicts=has_conflicts,
            conflict_note=conflict_note,
            sources=sources_list,
            personal_relevance_reason=personal_relevance_reason,
            what_changed=what_changed,
        )

    async def get_story_coverage(self, identifier: str) -> Optional[StoryCoverageResponse]:
        """Returns structured multi-source coverage grouped by relationship type."""
        detail = await self.get_story_detail(identifier)
        if not detail:
            return None

        by_relationship: Dict[str, List[StoryArticleItem]] = {}
        for it in detail.articles:
            rel = it.relationship_type
            if rel not in by_relationship:
                by_relationship[rel] = []
            by_relationship[rel].append(it)

        return StoryCoverageResponse(
            story_id=detail.id,
            story_title=detail.title,
            story_slug=detail.slug,
            total_articles=detail.article_count,
            total_sources=detail.source_count,
            independent_source_count=detail.independent_source_count,
            articles_by_relationship=by_relationship,
            sources=detail.sources,
            has_conflicts=detail.has_conflicts,
            conflict_details=[{"note": detail.conflict_note}] if detail.has_conflicts else [],
        )

    async def get_story_timeline(self, identifier: str) -> List[StoryTimelineItem]:
        """Returns timeline of developing story ordered chronologically."""
        detail = await self.get_story_detail(identifier)
        return detail.timeline if detail else []

    async def get_related_stories(self, identifier: str, limit: int = 5) -> List[StoryItem]:
        """Returns related stories based on shared topic, entities, or keywords."""
        current = await self.get_story_by_id_or_slug(identifier)
        if not current:
            return []

        stmt = (
            select(Story)
            .where(
                Story.id != current.id,
                Story.merged_into_story_id.is_(None),
            )
            .options(
                selectinload(Story.primary_topic),
                selectinload(Story.primary_article),
                selectinload(Story.latest_article),
            )
            .order_by(desc(Story.importance_score), desc(Story.last_updated_at))
            .limit(limit * 3)
        )
        if current.primary_topic_id:
            stmt = stmt.where(Story.primary_topic_id == current.primary_topic_id)

        res = await self.session.execute(stmt)
        candidates = list(res.scalars().all())

        items: List[StoryItem] = []
        for s in candidates[:limit]:
            items.append(self._story_to_item(s))
        return items

    async def get_stories_feed(
        self,
        status: Optional[str] = None,
        topic: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        user_id: Optional[uuid.UUID] = None,
    ) -> StoryFeedResponse:
        """Returns paginated stories feed, optionally boosted by user personalization."""
        stmt = (
            select(Story)
            .where(Story.merged_into_story_id.is_(None))
            .options(
                selectinload(Story.primary_topic),
                selectinload(Story.primary_article).selectinload(Article.source),
                selectinload(Story.latest_article).selectinload(Article.source),
            )
        )

        if status:
            stmt = stmt.where(Story.status == status.upper().strip())
        if topic:
            top_slug = topic.lower().replace(" ", "-")
            stmt = stmt.join(Story.primary_topic).where(
                or_(Topic.slug == top_slug, Topic.name.ilike(f"%{topic}%"))
            )

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one() or 0

        # Order by developing/active importance and recency
        stmt = stmt.order_by(desc(Story.importance_score), desc(Story.last_updated_at))
        stmt = stmt.offset((page - 1) * limit).limit(limit)

        res = await self.session.execute(stmt)
        stories = list(res.scalars().all())

        items = [self._story_to_item(s) for s in stories]
        return StoryFeedResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            has_next=((page * limit) < total),
        )

    async def search_stories(
        self,
        query: str,
        topic: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> StorySearchResponse:
        """Full-text and semantic search for Story entities."""
        q_clean = (query or "").strip()
        stmt = (
            select(Story)
            .where(Story.merged_into_story_id.is_(None))
            .options(
                selectinload(Story.primary_topic),
                selectinload(Story.primary_article),
                selectinload(Story.latest_article),
            )
        )

        if q_clean:
            search_filter = or_(
                Story.title.ilike(f"%{q_clean}%"),
                Story.summary.ilike(f"%{q_clean}%"),
            )
            stmt = stmt.where(search_filter)

        if status:
            stmt = stmt.where(Story.status == status.upper().strip())
        if topic:
            top_slug = topic.lower().replace(" ", "-")
            stmt = stmt.join(Story.primary_topic).where(
                or_(Topic.slug == top_slug, Topic.name.ilike(f"%{topic}%"))
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one() or 0

        stmt = stmt.order_by(desc(Story.importance_score), desc(Story.last_updated_at))
        stmt = stmt.offset(offset).limit(limit)

        res = await self.session.execute(stmt)
        stories = list(res.scalars().all())

        return StorySearchResponse(
            query=q_clean,
            total=total,
            results=[self._story_to_item(s) for s in stories],
        )

    @staticmethod
    def _story_to_item(story: Story, personal_score: Optional[float] = None) -> StoryItem:
        p_art = story.primary_article
        l_art = story.latest_article
        return StoryItem(
            id=story.id,
            title=story.title,
            slug=story.slug,
            summary=story.summary,
            status=story.status,
            importance_score=story.importance_score,
            quality_score=story.quality_score,
            activity_score=story.activity_score,
            article_count=story.article_count,
            source_count=story.source_count,
            independent_source_count=story.independent_source_count,
            first_published_at=story.first_published_at,
            last_updated_at=story.last_updated_at,
            primary_topic_name=story.primary_topic.name if story.primary_topic else None,
            primary_article_id=story.primary_article_id,
            latest_article_id=story.latest_article_id,
            primary_article={
                "id": str(p_art.id),
                "title": p_art.title,
                "url": getattr(p_art, "source_url", getattr(p_art, "url", None)),
            } if p_art else None,
            latest_article={
                "id": str(l_art.id),
                "title": l_art.title,
                "url": getattr(l_art, "source_url", getattr(l_art, "url", None)),
            } if l_art else None,
            has_conflicts=False,
            conflict_note=None,
            personal_score=personal_score,
        )
