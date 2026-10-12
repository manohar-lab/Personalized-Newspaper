"""search.py — Phase 24 Search API Endpoints."""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.api.deps import get_current_user, get_optional_current_user
from app.models.user import User
from app.search.search_service import SearchService
from app.search.schemas import (
    SearchFilterParams,
    SearchResponse,
    SearchSuggestionsResponse,
    SearchHistoryResponse,
    SearchRecentResponse,
    SearchFiltersMetaResponse,
)

router = APIRouter()


@router.get("", response_model=SearchResponse, summary="Execute intelligent personalized news search")
async def search_articles(
    q: str = Query(default="", description="Search query string"),
    topic: Optional[str] = Query(default=None, description="Topic slug or name filter"),
    category: Optional[str] = Query(default=None, description="Primary category filter"),
    source: Optional[str] = Query(default=None, description="Source name filter (single or comma-separated)"),
    date_from: Optional[datetime] = Query(default=None, description="Published on or after (ISO datetime)"),
    date_to: Optional[datetime] = Query(default=None, description="Published on or before (ISO datetime)"),
    date_preset: Optional[str] = Query(default=None, description="today | yesterday | last_24_hours | last_7_days | last_30_days"),
    article_type: Optional[str] = Query(default=None, description="Article type filter"),
    language: Optional[str] = Query(default=None, description="Language filter"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=50, description="Page size"),
    sort_by: Optional[str] = Query(default="relevance", description="relevance | newest | importance"),
    read_status: Optional[str] = Query(default=None, description="all | read | unread"),
    saved_status: Optional[str] = Query(default=None, description="all | saved | unsaved"),
    result_type: Optional[str] = Query(default="ALL", description="ALL | STORIES | ARTICLES | TOPICS | ENTITIES"),
    deduplicate: bool = Query(default=True, description="Deduplicate articles covering identical headlines or same story"),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """
    Executes hybrid search combining stories, articles, topics, and entities.
    Prioritizes results using query relevance, semantic similarity, publication freshness,
    story importance, and user personalization profile.
    """
    params = SearchFilterParams(
        q=q,
        topic=topic,
        category=category,
        source=source,
        date_from=date_from,
        date_to=date_to,
        date_preset=date_preset,
        article_type=article_type,
        language=language,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        read_status=read_status,
        saved_status=saved_status,
        result_type=result_type,
        deduplicate=deduplicate,
    )
    service = SearchService(db)
    user_id = current_user.id if current_user else None
    return await service.search(params=params, user_id=user_id)


@router.get("/suggestions", response_model=SearchSuggestionsResponse, summary="Get autocomplete search suggestions")
async def get_search_suggestions(
    q: str = Query(default="", description="Query prefix"),
    limit: int = Query(default=8, ge=1, le=20),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchSuggestionsResponse:
    """Returns autocomplete suggestions from topics, entities, stories, and the user's private history."""
    service = SearchService(db)
    user_id = current_user.id if current_user else None
    return await service.get_suggestions(query=q, user_id=user_id, limit=limit)


@router.get("/filters", response_model=SearchFiltersMetaResponse, summary="Get available search filters metadata")
async def get_search_filters(
    db: AsyncSession = Depends(get_db),
) -> SearchFiltersMetaResponse:
    """Returns available categories, date presets, sorting choices, and sources."""
    service = SearchService(db)
    return await service.get_filters_metadata()


@router.get("/recent", response_model=SearchRecentResponse, summary="Get user recent searches")
async def get_recent_searches(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchRecentResponse:
    """Returns past search queries for the authenticated user only (user isolated)."""
    service = SearchService(db)
    return await service.get_user_recent_searches(user_id=current_user.id, limit=limit)


@router.delete("/recent", summary="Clear user recent searches")
async def clear_recent_searches(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Clears all search history for the authenticated user only."""
    service = SearchService(db)
    return await service.clear_user_search_history(user_id=current_user.id)


@router.get("/history", response_model=SearchHistoryResponse, summary="Get user search history")
async def get_search_history(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchHistoryResponse:
    """Backward-compatible endpoint for user search history."""
    service = SearchService(db)
    return await service.get_user_search_history(user_id=current_user.id, limit=limit)


@router.delete("/history", summary="Clear user search history")
async def clear_search_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Backward-compatible endpoint to clear user search history."""
    service = SearchService(db)
    return await service.clear_user_search_history(user_id=current_user.id)
