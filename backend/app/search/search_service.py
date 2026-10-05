"""search_service.py — Phase 11 Intelligent Personalized Search Service."""
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import delete, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.article import Article
from app.models.analysis import ArticleAnalysis
from app.models.topic import Topic
from app.models.entity import Entity
from app.models.source import NewsSource
from app.models.search import UserSearchHistory
from app.personalization.services.personalization_service import PersonalizationService
from app.search.schemas import (
    SearchFilterParams,
    SearchResultItem,
    SearchResponse,
    SearchSuggestionItem,
    SearchSuggestionsResponse,
    SearchHistoryItem,
    SearchHistoryResponse,
)
from app.search.query_parser import QueryParser
from app.search.keyword_search import FullTextSearchEngine
from app.search.semantic_search import SemanticSearchEngine
from app.search.ranking import HybridSearchRanker

logger = logging.getLogger(__name__)


class SearchService:
    """
    Coordinates intelligent personalized search across full-text, semantic vectors,
    topic/entity metadata, and user personalization profiles.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.full_text_engine = FullTextSearchEngine(session)
        self.semantic_engine = SemanticSearchEngine(session)
        self.ranker = HybridSearchRanker()
        self.personalization_service = PersonalizationService(session)

    async def search(
        self,
        params: SearchFilterParams,
        user_id: Optional[uuid.UUID] = None,
    ) -> SearchResponse:
        """
        Executes hybrid full-text and semantic vector search with personalization boosts and filters.
        """
        start_time = time.perf_counter()
        raw_query = params.q.strip()

        # 1. Deterministic Query Parsing
        parsed_query, parsed_date_from, parsed_date_to = QueryParser.parse_query(raw_query)

        # 2. Build Base Filtered Query
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
        effective_topic = params.topic or (parsed_query.detected_topics[0] if len(parsed_query.detected_topics) == 1 and not raw_query else None)
        if effective_topic:
            top_slug = effective_topic.lower().replace(" ", "-")
            base_stmt = base_stmt.where(
                Article.topics.any(or_(Topic.slug == top_slug, Topic.name.ilike(f"%{effective_topic}%")))
            )

        # Filters: Category
        if params.category:
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

        # Filters: Date Range
        effective_date_from = params.date_from or parsed_date_from
        effective_date_to = params.date_to or parsed_date_to
        if effective_date_from:
            base_stmt = base_stmt.where(Article.published_at >= effective_date_from)
        if effective_date_to:
            base_stmt = base_stmt.where(Article.published_at <= effective_date_to)

        # Filters: Article Type
        if params.article_type:
            base_stmt = base_stmt.where(
                Article.analysis.has(ArticleAnalysis.article_type.ilike(params.article_type.strip()))
            )

        # Filters: Language
        if params.language:
            base_stmt = base_stmt.where(Article.language == params.language.strip())

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

        # 5. Personal Relevance Scoring
        personal_scores: Dict[uuid.UUID, float] = {}
        has_user_interests = False

        if user_id:
            try:
                profile = await self.personalization_service.get_user_interest_profile(user_id)
                has_user_interests = profile.has_interests
                now_dt = datetime.now(timezone.utc)
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
            except Exception as e:
                logger.warning(f"Error computing search personalization: {e}")

        # 6. Hybrid Ranking
        ranked_items = self.ranker.rank_results(
            articles=candidate_articles,
            full_text_scores=ft_scores,
            semantic_scores=sem_scores,
            personal_relevance_scores=personal_scores,
            parsed_query=parsed_query,
            has_user_profile=has_user_interests,
        )

        # 7. Pagination
        total_results = len(ranked_items)
        page = max(1, params.page)
        page_size = min(settings.SEARCH_MAX_PAGE_SIZE, max(1, params.page_size))
        total_pages = max(1, (total_results + page_size - 1) // page_size)

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_items = ranked_items[start_idx:end_idx]

        execution_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        # 8. Record Search History (if authenticated and query non-empty)
        if user_id and raw_query:
            try:
                history_record = UserSearchHistory(
                    user_id=user_id,
                    query=raw_query,
                    filters=json.dumps(params.model_dump(exclude={"q", "page", "page_size"}, exclude_none=True)),
                    result_count=total_results,
                )
                self.session.add(history_record)
                await self.session.commit()
            except Exception as e:
                logger.warning(f"Failed to record search history: {e}")

        return SearchResponse(
            query=raw_query,
            total_results=total_results,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            results=paginated_items,
            parsed_query=parsed_query,
            execution_time_ms=execution_ms,
        )

    # -------------------------------------------------------------------------
    # Search Suggestions & Autocomplete
    # -------------------------------------------------------------------------
    async def get_suggestions(self, query: str, limit: int = 8) -> SearchSuggestionsResponse:
        """Returns autocomplete suggestions from topics, entities, and recent search history."""
        clean_q = query.strip()
        if not clean_q:
            return SearchSuggestionsResponse(query="", suggestions=[])

        suggestions: List[SearchSuggestionItem] = []
        seen_texts = set()

        # 1. Matching Topics
        stmt_topics = select(Topic).where(Topic.name.ilike(f"%{clean_q}%")).limit(4)
        res_topics = await self.session.execute(stmt_topics)
        for t in res_topics.scalars().all():
            if t.name.lower() not in seen_texts:
                seen_texts.add(t.name.lower())
                suggestions.append(SearchSuggestionItem(text=t.name, type="TOPIC", subtitle="Topic"))

        # 2. Matching Entities
        stmt_entities = select(Entity).where(Entity.name.ilike(f"%{clean_q}%")).limit(4)
        res_entities = await self.session.execute(stmt_entities)
        for e in res_entities.scalars().all():
            if e.name.lower() not in seen_texts:
                seen_texts.add(e.name.lower())
                suggestions.append(SearchSuggestionItem(text=e.name, type="ENTITY", subtitle=f"Entity ({e.entity_type})"))

        # 3. Matching Recent Searches
        stmt_hist = (
            select(UserSearchHistory.query)
            .where(UserSearchHistory.query.ilike(f"%{clean_q}%"))
            .distinct()
            .limit(3)
        )
        res_hist = await self.session.execute(stmt_hist)
        for h in res_hist.scalars().all():
            if h.lower() not in seen_texts:
                seen_texts.add(h.lower())
                suggestions.append(SearchSuggestionItem(text=h, type="RECENT", subtitle="Recent Search"))

        return SearchSuggestionsResponse(
            query=clean_q,
            suggestions=suggestions[:limit],
        )

    # -------------------------------------------------------------------------
    # Search History Management
    # -------------------------------------------------------------------------
    async def get_user_search_history(
        self,
        user_id: uuid.UUID,
        limit: int = 20,
    ) -> SearchHistoryResponse:
        """Retrieves past search history for a user."""
        stmt = (
            select(UserSearchHistory)
            .where(UserSearchHistory.user_id == user_id)
            .order_by(desc(UserSearchHistory.created_at))
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        records = res.scalars().all()
        return SearchHistoryResponse(
            history=[
                SearchHistoryItem(
                    id=r.id,
                    query=r.query,
                    filters=r.filters,
                    result_count=r.result_count,
                    created_at=r.created_at,
                )
                for r in records
            ]
        )

    async def clear_user_search_history(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """Clears all search history for a user."""
        stmt = delete(UserSearchHistory).where(UserSearchHistory.user_id == user_id)
        res = await self.session.execute(stmt)
        await self.session.commit()
        deleted_count = res.rowcount if hasattr(res, "rowcount") else 0
        return {"success": True, "deleted_count": deleted_count}
