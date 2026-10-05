import uuid
import logging
from typing import Optional, Tuple
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.article import Article
from app.ingestion.rss.normalizer import NormalizedArticle

logger = logging.getLogger(__name__)


class ArticleDeduplicator:
    @staticmethod
    async def is_duplicate(
        session: AsyncSession,
        article: NormalizedArticle,
        source_id: Optional[uuid.UUID] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Deduplication checks:
        1. Canonical URL match
        2. Source URL match (or crossed with canonical URL)
        3. Content hash match
        4. Same title + source combination
        """
        # 1. Check Canonical URL & Source URL match
        url_conditions = []
        if article.canonical_url:
            url_conditions.append(Article.canonical_url == article.canonical_url)
            url_conditions.append(Article.source_url == article.canonical_url)
        if article.url:
            url_conditions.append(Article.source_url == article.url)
            url_conditions.append(Article.canonical_url == article.url)

        if url_conditions:
            stmt_url = select(Article.id).where(or_(*url_conditions)).limit(1)
            result_url = await session.execute(stmt_url)
            if result_url.scalar_one_or_none():
                return True, "duplicate_url"

        # 2. Check Content Hash match
        if article.content_hash:
            stmt_hash = select(Article.id).where(
                Article.content_hash == article.content_hash
            ).limit(1)
            result_hash = await session.execute(stmt_hash)
            if result_hash.scalar_one_or_none():
                return True, "duplicate_content_hash"

        # 3. Check Title + Source combination
        if article.title:
            source_conditions = []
            if source_id:
                source_conditions.append(Article.source_id == source_id)
            if article.source_name:
                source_conditions.append(Article.source_name == article.source_name)

            if source_conditions:
                stmt_title = select(Article.id).where(
                    and_(
                        Article.title == article.title,
                        or_(*source_conditions),
                    )
                ).limit(1)
                result_title = await session.execute(stmt_title)
                if result_title.scalar_one_or_none():
                    return True, "duplicate_title_and_source"

        return False, None
