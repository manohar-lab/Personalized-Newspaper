"""search_service.py — Phase 24 Intelligent Personalized Search & Discovery Service."""
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import delete, desc, func, or_, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.article import Article
from app.models.analysis import ArticleAnalysis
from app.models.topic import Topic
from app.models.entity import Entity
from app.models.source import NewsSource
from app.models.search import UserSearchHistory
from app.models.interest import UserInterest
from app.models.reading_history import ReadingHistory
from app.models.action import UserArticleAction
from app.story_intelligence.models import Story, StoryArticle
from app.personalization.services.personalization_service import PersonalizationService
from app.learning.behavioral_engine import BehavioralLearningEngine
from app.search.schemas import (
    SearchFilterParams,
    SearchResultItem,
    SearchStoryItem,
    SearchTopicItem,
    SearchEntityItem,
    SearchResponse,
    SearchSuggestionItem,
    SearchSuggestionsResponse,
    SearchHistoryItem,
    SearchHistoryResponse,
    SearchRecentResponse,
    SearchFiltersMetaResponse,
)
from app.search.query_parser import QueryParser
from app.search.keyword_search import FullTextSearchEngine
from app.search.semantic_search import SemanticSearchEngine
from app.search.ranking import HybridSearchRanker

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SearchService:
    """
    Coordinates intelligent personalized search across full-text, semantic vectors,
    stories, topics, entities, user preferences, and behavioral analytics.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.full_text_engine = FullTextSearchEngine(session)
        self.semantic_engine = SemanticSearchEngine(session)
        self.ranker = HybridSearchRanker()
        self.personalization_service = PersonalizationService(session)
        self.behavioral_engine = BehavioralLearningEngine(session)

    async def search(
        self,
        params: SearchFilterParams,
        user_id: Optional[uuid.UUID] = None,
    ) -> SearchResponse:
        """
        Executes hybrid search across stories, articles, topics, and entities with personalization and filters.
        """
        start_time = time.perf_counter()
        raw_query = QueryParser.normalize_query(params.q)

        # 1. Deterministic Query Parsing & Normalization
        parsed_query, parsed_date_from, parsed_date_to = QueryParser.parse_query(raw_query)

        # 2. Build Base Filtered Query for Articles
        base_stmt = (
            select(Article)
            .where(Article.status == "PUBLISHED")
            .options(
                selectinload(Article.topics),
                selectinload(Article.analysis),
                selectinload(Article.entities),
                selectinload(Article.keywords),
                selectinload(Article.source),
            )
            .execution_options(populate_existing=True)
        )

        # Filters: Topic
        effective_topic = params.topic or (
            parsed_query.detected_topics[0]
            if len(parsed_query.detected_topics) == 1 and not raw_query
            else None
        )
        if effective_topic:
            top_slug = effective_topic.lower().replace(" ", "-")
            base_stmt = base_stmt.where(
                Article.topics.any(or_(Topic.slug == top_slug, Topic.name.ilike(f"%{effective_topic}%")))
            )

        # Filters: Category
        if params.category and params.category.upper() != "ALL":
            base_stmt = base_stmt.where(
                Article.analysis.has(ArticleAnalysis.primary_category.ilike(params.category.strip()))
            )

        # Filters: Source
        if params.source:
            sources = [s.strip() for s in params.source.split(",") if s.strip()]
            if sources:
                base_stmt = base_stmt.where(
                    or_(
                        Article.source_name.in_(sources),
                        Article.source.has(
                            or_(
                                NewsSource.name.in_(sources),
                                NewsSource.slug.in_([s.lower().replace(" ", "-") for s in sources]),
                            )
                        ),
                    )
                )

        # Filters: Date Presets & Custom Date Range
        now_utc = utc_now()
        effective_date_from = params.date_from or parsed_date_from
        effective_date_to = params.date_to or parsed_date_to

        if params.date_preset:
            preset = params.date_preset.lower().strip()
            if preset == "today":
                effective_date_from = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
            elif preset == "yesterday":
                effective_date_from = (now_utc - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                effective_date_to = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
            elif preset in ("last_24_hours", "24h"):
                effective_date_from = now_utc - timedelta(hours=24)
            elif preset == "last_7_days":
                effective_date_from = now_utc - timedelta(days=7)
            elif preset == "last_30_days":
                effective_date_from = now_utc - timedelta(days=30)

        if effective_date_from:
            base_stmt = base_stmt.where(
                and_(Article.published_at.isnot(None), Article.published_at >= effective_date_from)
            )
        if effective_date_to:
            base_stmt = base_stmt.where(
                and_(Article.published_at.isnot(None), Article.published_at <= effective_date_to)
            )

        # Filters: Article Type
        if params.article_type:
            base_stmt = base_stmt.where(
                Article.analysis.has(ArticleAnalysis.article_type.ilike(params.article_type.strip()))
            )

        # Filters: Language
        if params.language:
            base_stmt = base_stmt.where(Article.language == params.language.strip().lower())

        # Filters: Read / Unread Status (authenticated only)
        if params.read_status and user_id:
            read_subquery = select(ReadingHistory.article_id).where(ReadingHistory.user_id == user_id)
            if params.read_status.lower() == "read":
                base_stmt = base_stmt.where(Article.id.in_(read_subquery))
            elif params.read_status.lower() == "unread":
                base_stmt = base_stmt.where(Article.id.not_in(read_subquery))

        # Filters: Saved / Unsaved Status (authenticated only)
        if params.saved_status and user_id:
            saved_subquery = select(UserArticleAction.article_id).where(
                UserArticleAction.user_id == user_id,
                UserArticleAction.action == "SAVE",
            )
            if params.saved_status.lower() == "saved":
                base_stmt = base_stmt.where(Article.id.in_(saved_subquery))
            elif params.saved_status.lower() == "unsaved":
                base_stmt = base_stmt.where(Article.id.not_in(saved_subquery))

        # 3. Full-Text Search Retrieval & Scoring
        ft_results = await self.full_text_engine.search_full_text(
            query=parsed_query.clean_keywords,
            base_stmt=base_stmt,
        )

        candidate_articles = [item[0] for item in ft_results]
        ft_scores = {art.id: score for art, score in ft_results}

        # 4. Semantic Search Vector Scoring
        sem_scores = await self.semantic_engine.score_articles_semantically(
            query=parsed_query.clean_keywords,
            articles=candidate_articles,
        )

        # 5. Personal Relevance Scoring & Mutes
        personal_scores: Dict[uuid.UUID, float] = {}
        has_user_interests = False
        muted_topics: Set[str] = set()
        muted_sources: Set[str] = set()

        if user_id:
            try:
                profile = await self.personalization_service.get_user_interest_profile(user_id)
                has_user_interests = profile.has_interests
                now_dt = utc_now()
                for art in candidate_articles:
                    score, _ = self.personalization_service.scorer.compute_relevance(
                        article=art,
                        positive_interests=profile.positive_interests,
                        negative_interests=profile.negative_interests,
                        user_embedding=profile.embedding,
                        positive_topic_names=list(profile.topic_names_map.values()),
                        now=now_dt,
                    )
                    personal_scores[art.id] = score

                # Load muted topics
                for neg_t in profile.negative_interests:
                    muted_topics.add(neg_t.lower())
            except Exception as e:
                logger.warning(f"Error computing search personalization: {e}")

        # 6. Hybrid Ranking & Sorting
        ranked_items = self.ranker.rank_results(
            articles=candidate_articles,
            full_text_scores=ft_scores,
            semantic_scores=sem_scores,
            personal_relevance_scores=personal_scores,
            parsed_query=parsed_query,
            has_user_profile=has_user_interests,
            sort_by=params.sort_by or "relevance",
            muted_topics=muted_topics,
            muted_sources=muted_sources,
        )

        # Deduplicate articles if requested
        if params.deduplicate:
            seen_titles = set()
            deduped_items = []
            for item in ranked_items:
                norm_t = re.sub(r"\W+", " ", item.title.lower()).strip()
                if norm_t not in seen_titles:
                    seen_titles.add(norm_t)
                    deduped_items.append(item)
            ranked_items = deduped_items

        # 7. Multi-Entity / Multi-Domain Retrieval
        matching_stories: List[SearchStoryItem] = []
        matching_topics: List[SearchTopicItem] = []
        matching_entities: List[SearchEntityItem] = []

        # Retrieve Stories
        if raw_query:
            try:
                story_stmt = (
                    select(Story)
                    .where(
                        Story.merged_into_story_id.is_(None),
                        or_(
                            Story.title.ilike(f"%{raw_query}%"),
                            Story.summary.ilike(f"%{raw_query}%"),
                            Story.primary_topic.has(Topic.name.ilike(f"%{raw_query}%")),
                        ),
                    )
                    .options(selectinload(Story.primary_topic))
                    .order_by(desc(Story.importance_score), desc(Story.last_updated_at))
                    .limit(6)
                )
                story_res = await self.session.execute(story_stmt)
                for s in story_res.scalars().all():
                    matching_stories.append(
                        SearchStoryItem(
                            id=s.id,
                            title=s.title,
                            slug=s.slug,
                            summary=s.summary,
                            article_count=s.article_count,
                            source_count=s.source_count,
                            status=s.status,
                            importance_score=s.importance_score,
                            last_updated_at=s.last_updated_at,
                            first_published_at=s.first_published_at,
                            primary_topic_name=s.primary_topic.name if s.primary_topic else None,
                            read_story_link=f"/stories/{s.slug}",
                        )
                    )
            except Exception as e:
                logger.warning(f"Error querying stories for search: {e}")

        # Retrieve Topics
        if raw_query:
            try:
                topic_stmt = (
                    select(Topic)
                    .where(
                        or_(
                            Topic.name.ilike(f"%{raw_query}%"),
                            Topic.slug.ilike(f"%{raw_query.lower().replace(' ', '-')}%"),
                        )
                    )
                    .limit(6)
                )
                topic_res = await self.session.execute(topic_stmt)
                matching_topic_objs = list(topic_res.scalars().all())

                user_followed_topic_ids = set()
                if user_id:
                    ui_stmt = select(UserInterest.topic_id).where(
                        UserInterest.user_id == user_id,
                        UserInterest.preference_type == "POSITIVE",
                    )
                    ui_res = await self.session.execute(ui_stmt)
                    user_followed_topic_ids = set(ui_res.scalars().all())

                for t in matching_topic_objs:
                    matching_topics.append(
                        SearchTopicItem(
                            id=t.id,
                            name=t.name,
                            slug=t.slug,
                            description=t.description,
                            is_followed=(t.id in user_followed_topic_ids),
                            article_count=0,
                        )
                    )
            except Exception as e:
                logger.warning(f"Error querying topics for search: {e}")

        # Retrieve Entities
        if raw_query:
            try:
                entity_stmt = (
                    select(Entity)
                    .where(
                        or_(
                            Entity.name.ilike(f"%{raw_query}%"),
                            Entity.normalized_name.ilike(f"%{raw_query.lower()}%"),
                        )
                    )
                    .limit(6)
                )
                entity_res = await self.session.execute(entity_stmt)
                for ent in entity_res.scalars().all():
                    matching_entities.append(
                        SearchEntityItem(
                            id=ent.id,
                            name=ent.name,
                            entity_type=ent.entity_type,
                            is_followed=False,
                            is_muted=False,
                            story_count=0,
                            article_count=0,
                        )
                    )
            except Exception as e:
                logger.warning(f"Error querying entities for search: {e}")

        # Filter by result_type if specified
        res_type = (params.result_type or "ALL").upper().strip()
        final_articles = ranked_items if res_type in ("ALL", "ARTICLES") else []
        final_stories = matching_stories if res_type in ("ALL", "STORIES") else []
        final_topics = matching_topics if res_type in ("ALL", "TOPICS") else []
        final_entities = matching_entities if res_type in ("ALL", "ENTITIES") else []

        # 8. Pagination for Articles
        total_results = len(final_articles)
        page = max(1, params.page)
        page_size = min(settings.SEARCH_MAX_PAGE_SIZE, max(1, params.page_size))
        total_pages = max(1, (total_results + page_size - 1) // page_size)

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_articles = final_articles[start_idx:end_idx]

        execution_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        # 9. Record Search History & Behavioral Learning
        if user_id and raw_query:
            try:
                # Enforce limit of retained searches per user (max 50)
                history_record = UserSearchHistory(
                    user_id=user_id,
                    query=raw_query,
                    normalized_query=parsed_query.clean_keywords,
                    filters=json.dumps(
                        params.model_dump(
                            exclude={"q", "page", "page_size"},
                            exclude_none=True,
                            mode="json",
                        )
                    ),
                    result_count=total_results,
                )
                self.session.add(history_record)

                # Prune older records beyond 50
                count_stmt = select(func.count(UserSearchHistory.id)).where(UserSearchHistory.user_id == user_id)
                curr_count = (await self.session.execute(count_stmt)).scalar() or 0
                if curr_count >= 50:
                    old_ids_stmt = (
                        select(UserSearchHistory.id)
                        .where(UserSearchHistory.user_id == user_id)
                        .order_by(UserSearchHistory.created_at.asc())
                        .limit(curr_count - 49)
                    )
                    old_ids = (await self.session.execute(old_ids_stmt)).scalars().all()
                    if old_ids:
                        await self.session.execute(
                            delete(UserSearchHistory).where(UserSearchHistory.id.in_(old_ids))
                        )

                # Record Behavioral Learning Evidence (respects paused learning)
                await self.behavioral_engine.record_evidence(
                    user_id=user_id,
                    signal_type="SEARCH",
                    target_type="QUERY",
                    target_name=raw_query,
                    event_metadata={"clean_keywords": parsed_query.clean_keywords},
                    commit=False,
                )

                await self.session.commit()
            except Exception as e:
                logger.warning(f"Failed to record search history / behavioral evidence: {e}")
                await self.session.rollback()

        total_counts = {
            "stories": len(matching_stories),
            "articles": len(ranked_items),
            "topics": len(matching_topics),
            "entities": len(matching_entities),
        }

        applied_filters = {
            "category": params.category,
            "topic": params.topic,
            "source": params.source,
            "date_preset": params.date_preset,
            "date_from": effective_date_from.isoformat() if effective_date_from else None,
            "date_to": effective_date_to.isoformat() if effective_date_to else None,
            "sort_by": params.sort_by or "relevance",
            "read_status": params.read_status,
            "saved_status": params.saved_status,
            "result_type": params.result_type or "ALL",
        }

        query_metadata = {
            "raw_query": raw_query,
            "clean_keywords": parsed_query.clean_keywords,
            "detected_topics": parsed_query.detected_topics,
            "detected_entities": parsed_query.detected_entities,
            "date_range_detected": parsed_query.date_range_detected,
        }

        return SearchResponse(
            query=raw_query,
            total_results=total_results,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            results=paginated_articles,
            articles=paginated_articles,
            stories=final_stories,
            topics=final_topics,
            entities=final_entities,
            total_counts=total_counts,
            applied_filters=applied_filters,
            query_metadata=query_metadata,
            parsed_query=parsed_query,
            execution_time_ms=execution_ms,
        )

    # -------------------------------------------------------------------------
    # Search Suggestions & Autocomplete
    # -------------------------------------------------------------------------
    async def get_suggestions(
        self,
        query: str,
        user_id: Optional[uuid.UUID] = None,
        limit: int = 8,
    ) -> SearchSuggestionsResponse:
        """
        Returns autocomplete suggestions from topics, entities, stories, and the user's own search history.
        Enforces user privacy: never leaks another user's searches.
        """
        clean_q = QueryParser.normalize_query(query)
        if not clean_q or len(clean_q) < 2:
            return SearchSuggestionsResponse(query=clean_q, suggestions=[])

        suggestions: List[SearchSuggestionItem] = []
        seen_texts = set()

        # 1. Matching Topics
        stmt_topics = select(Topic).where(Topic.name.ilike(f"%{clean_q}%")).limit(3)
        res_topics = await self.session.execute(stmt_topics)
        for t in res_topics.scalars().all():
            if t.name.lower() not in seen_texts:
                seen_texts.add(t.name.lower())
                suggestions.append(SearchSuggestionItem(text=t.name, type="TOPIC", subtitle="Topic"))

        # 2. Matching Entities
        stmt_entities = select(Entity).where(Entity.name.ilike(f"%{clean_q}%")).limit(3)
        res_entities = await self.session.execute(stmt_entities)
        for e in res_entities.scalars().all():
            if e.name.lower() not in seen_texts:
                seen_texts.add(e.name.lower())
                suggestions.append(
                    SearchSuggestionItem(text=e.name, type="ENTITY", subtitle=f"Entity ({e.entity_type})")
                )

        # 3. Matching Stories
        stmt_stories = (
            select(Story.title)
            .where(Story.title.ilike(f"%{clean_q}%"), Story.merged_into_story_id.is_(None))
            .limit(2)
        )
        res_stories = await self.session.execute(stmt_stories)
        for s_title in res_stories.scalars().all():
            if s_title.lower() not in seen_texts:
                seen_texts.add(s_title.lower())
                suggestions.append(SearchSuggestionItem(text=s_title, type="STORY", subtitle="Story Headline"))

        # 4. User's Own Recent Searches (Privacy Protected)
        if user_id:
            stmt_hist = (
                select(UserSearchHistory.query)
                .where(
                    UserSearchHistory.user_id == user_id,
                    UserSearchHistory.query.ilike(f"%{clean_q}%"),
                )
                .distinct()
                .limit(3)
            )
            res_hist = await self.session.execute(stmt_hist)
            for h in res_hist.scalars().all():
                if h.lower() not in seen_texts:
                    seen_texts.add(h.lower())
                    suggestions.append(SearchSuggestionItem(text=h, type="RECENT", subtitle="Your Recent Search"))

        return SearchSuggestionsResponse(
            query=clean_q,
            suggestions=suggestions[:limit],
        )

    # -------------------------------------------------------------------------
    # Search History Management (User Ownership & Isolation)
    # -------------------------------------------------------------------------
    async def get_user_search_history(
        self,
        user_id: uuid.UUID,
        limit: int = 20,
    ) -> SearchHistoryResponse:
        """Retrieves past search history for the authenticated user only."""
        stmt = (
            select(UserSearchHistory)
            .where(UserSearchHistory.user_id == user_id)
            .order_by(desc(UserSearchHistory.created_at))
            .limit(min(100, max(1, limit)))
        )
        res = await self.session.execute(stmt)
        records = res.scalars().all()
        return SearchHistoryResponse(
            history=[
                SearchHistoryItem(
                    id=r.id,
                    query=r.query,
                    normalized_query=getattr(r, "normalized_query", None),
                    filters=r.filters,
                    result_count=r.result_count,
                    created_at=r.created_at,
                    searched_at=r.created_at,
                )
                for r in records
            ]
        )

    async def get_user_recent_searches(
        self,
        user_id: uuid.UUID,
        limit: int = 10,
    ) -> SearchRecentResponse:
        """Retrieves recent unique search queries for the authenticated user."""
        hist = await self.get_user_search_history(user_id=user_id, limit=limit)
        return SearchRecentResponse(recent=hist.history)

    async def clear_user_search_history(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """Clears search history exclusively for the authenticated user."""
        stmt = delete(UserSearchHistory).where(UserSearchHistory.user_id == user_id)
        res = await self.session.execute(stmt)
        await self.session.commit()
        deleted_count = res.rowcount if hasattr(res, "rowcount") else 0
        return {"success": True, "deleted_count": deleted_count}

    # -------------------------------------------------------------------------
    # Filter Metadata
    # -------------------------------------------------------------------------
    async def get_filters_metadata(self) -> SearchFiltersMetaResponse:
        """Returns available search filter presets and categories."""
        categories = [
            "ALL",
            "TECHNOLOGY",
            "SCIENCE",
            "BUSINESS",
            "FINANCE",
            "WORLD",
            "POLITICS",
            "HEALTH",
            "SPORTS",
            "ENTERTAINMENT",
        ]

        date_presets = [
            {"label": "All Time", "value": ""},
            {"label": "Today", "value": "today"},
            {"label": "Yesterday", "value": "yesterday"},
            {"label": "Last 24 Hours", "value": "last_24_hours"},
            {"label": "Last 7 Days", "value": "last_7_days"},
            {"label": "Last 30 Days", "value": "last_30_days"},
        ]

        sort_options = [
            {"label": "Most Relevant", "value": "relevance"},
            {"label": "Newest First", "value": "newest"},
            {"label": "Most Important", "value": "importance"},
        ]

        result_types = [
            {"label": "All Types", "value": "ALL"},
            {"label": "Stories", "value": "STORIES"},
            {"label": "Articles", "value": "ARTICLES"},
            {"label": "Topics", "value": "TOPICS"},
            {"label": "Entities", "value": "ENTITIES"},
        ]

        # Fetch distinct sources
        src_stmt = select(NewsSource.name).limit(20)
        src_res = await self.session.execute(src_stmt)
        sources = [s for s in src_res.scalars().all() if s]

        return SearchFiltersMetaResponse(
            categories=categories,
            date_presets=date_presets,
            languages=["en", "es", "fr", "de"],
            sources=sources,
            sort_options=sort_options,
            result_types=result_types,
        )
