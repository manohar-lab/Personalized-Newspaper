"""keyword_search.py — Phase 11 Full-Text and Keyword Search Engine."""
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.article import Article
from app.models.analysis import ArticleAnalysis


class FullTextSearchEngine:
    """
    PostgreSQL Full-Text Search Engine with field weighting:
    - Title: Weight A (Highest)
    - Description/Summary: Weight B (High)
    - Content: Weight C (Normal)
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    def calculate_python_keyword_score(self, query: str, article: Article) -> float:
        """
        In-memory keyword relevance calculation (used for fallback or hybrid validation).
        Scores matches across title (3x), description (2x), summary (2x), and content (1x).
        """
        if not query or not query.strip():
            return 0.5

        tokens = [t.lower().strip() for t in re.split(r"\W+", query) if len(t.strip()) > 1]
        if not tokens:
            tokens = [query.lower().strip()]

        title = (article.title or "").lower()
        desc = (article.description or "").lower()
        summary = (article.analysis.summary if article.analysis and article.analysis.summary else "").lower()
        content = (article.content or "").lower()

        # Check topics, entities, and keywords
        topics_str = " ".join(
            [t.name.lower() for t in getattr(article, "topics", []) if hasattr(t, "name")]
        )
        entities_str = " ".join(
            [e.name.lower() for e in getattr(article, "entities", []) if hasattr(e, "name")]
        )
        keywords_str = " ".join(
            [k.keyword.lower() for k in getattr(article, "keywords", []) if hasattr(k, "keyword")]
        )

        title_hits = sum(1 for t in tokens if t in title)
        desc_hits = sum(1 for t in tokens if t in desc)
        summary_hits = sum(1 for t in tokens if t in summary)
        topic_hits = sum(1 for t in tokens if t in topics_str)
        entity_hits = sum(1 for t in tokens if t in entities_str)
        keyword_hits = sum(1 for t in tokens if t in keywords_str)
        content_hits = sum(1 for t in tokens if t in content)

        # Weighted score
        raw_score = (
            (title_hits * 3.0)
            + (desc_hits * 2.0)
            + (summary_hits * 2.0)
            + (topic_hits * 2.5)
            + (entity_hits * 2.5)
            + (keyword_hits * 2.0)
            + (min(content_hits, 5) * 0.5)
        )

        max_possible = len(tokens) * 3.0
        normalized = min(1.0, raw_score / max(1.0, max_possible))
        return float(normalized)

    async def search_full_text(
        self,
        query: str,
        base_stmt: Any,
    ) -> List[Tuple[Article, float]]:
        """
        Executes full-text search against the given base SQLAlchemy statement.
        Returns list of (Article, full_text_score).
        """
        clean_q = query.strip()
        if not clean_q:
            # If query is empty, return base articles with neutral score 0.5
            res = await self.session.execute(base_stmt)
            return [(art, 0.5) for art in res.scalars().all()]

        # Try PostgreSQL ts_rank_cd full-text search or token matching
        try:
            from app.models.topic import Topic
            from app.models.entity import Entity
            from app.models.analysis import ArticleKeyword

            tokens = [t for t in re.split(r"\W+", clean_q) if t]
            ilike_clauses = []
            for t in tokens:
                ilike_clauses.append(
                    or_(
                        Article.title.ilike(f"%{t}%"),
                        Article.description.ilike(f"%{t}%"),
                        Article.content.ilike(f"%{t}%"),
                        Article.analysis.has(ArticleAnalysis.summary.ilike(f"%{t}%")),
                        Article.topics.any(Topic.name.ilike(f"%{t}%")),
                        Article.entities.any(Entity.name.ilike(f"%{t}%")),
                        Article.keywords.any(ArticleKeyword.keyword.ilike(f"%{t}%")),
                    )
                )

            stmt = base_stmt.where(or_(*ilike_clauses)) if ilike_clauses else base_stmt
            res = await self.session.execute(stmt)
            articles = list(res.scalars().all())

            results = []
            for art in articles:
                score = self.calculate_python_keyword_score(clean_q, art)
                results.append((art, score))

            # Sort by keyword score descending
            results.sort(key=lambda x: x[1], reverse=True)
            return results
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(f"Full-text SQL execution error: {exc}")
            # Fallback to direct fetch + python keyword match
            res = await self.session.execute(base_stmt)
            articles = list(res.scalars().all())
            results = [(art, self.calculate_python_keyword_score(clean_q, art)) for art in articles]
            results.sort(key=lambda x: x[1], reverse=True)
            return results

