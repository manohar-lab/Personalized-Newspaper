"""article_analysis_service.py — Phase 7 AI Article Analysis Orchestration Service.

Orchestrates the end-to-end AI analysis pipeline for articles:
Classification, Summarization, Topic Linking (with confidence), Entity Resolution,
Keyword Extraction, Importance Scoring, and Semantic Vector Embeddings.
"""
import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, or_, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import ArticleAnalyzer
from app.ai.classification.classifier import TopicClassifier
from app.ai.classification.schemas import (
    ArticleAnalysisOutput,
    ArticleType,
    PrimaryCategory,
)
from app.ai.embeddings.embedder import EmbeddingService
from app.ai.entities.extractor import EntityResolver
from app.ai.providers.factory import get_article_analyzer, get_embedding_provider
from app.core.config import settings
from app.models.analysis import ArticleAnalysis, ArticleKeyword
from app.models.article import Article

logger = logging.getLogger(__name__)


class ArticleAnalysisService:
    """End-to-end AI understanding, classification, and embedding orchestration service."""

    def __init__(
        self,
        session: AsyncSession,
        analyzer: Optional[ArticleAnalyzer] = None,
        embedding_service: Optional[EmbeddingService] = None,
        topic_classifier: Optional[TopicClassifier] = None,
        entity_resolver: Optional[EntityResolver] = None,
    ):
        self.session = session
        self.analyzer = analyzer or get_article_analyzer()
        self.embedding_service = embedding_service or EmbeddingService(get_embedding_provider())
        self.topic_classifier = topic_classifier or TopicClassifier(session)
        self.entity_resolver = entity_resolver or EntityResolver(session)
        self.analysis_version = getattr(settings, "ANALYSIS_VERSION", "v1")

    async def analyze_article(
        self,
        article_id: uuid.UUID,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Analyze a single article by ID.
        
        Args:
            article_id: UUID of article to analyze.
            force: If True, re-analyze even if already analyzed under current version.
            
        Returns:
            Dictionary containing analysis results and status.
        """
        start_time = time.time()

        # 1. Load article with relationships
        stmt = (
            select(Article)
            .options(
                selectinload(Article.analysis),
                selectinload(Article.topics),
                selectinload(Article.entities),
                selectinload(Article.keywords),
            )
            .where(Article.id == article_id)
        )
        res = await self.session.execute(stmt)
        article = res.scalar_one_or_none()

        if not article:
            logger.warning(f"Analysis requested for non-existent article: {article_id}")
            return {
                "article_id": str(article_id),
                "status": "FAILED",
                "error": "Article not found",
            }

        # 2. Check existing analysis cache / idempotency
        analysis = article.analysis
        if analysis and not force:
            if (
                analysis.analysis_status == "SUCCESS"
                and analysis.analysis_version == self.analysis_version
            ):
                return {
                    "article_id": str(article.id),
                    "status": "SUCCESS",
                    "primary_category": analysis.primary_category,
                    "article_type": analysis.article_type,
                    "importance_score": analysis.importance_score,
                    "summary": analysis.summary,
                    "language": analysis.language,
                    "analysis_version": analysis.analysis_version,
                    "has_embedding": analysis.embedding is not None,
                    "already_analyzed": True,
                }

        # Create or update ArticleAnalysis record to PENDING / PROCESSING
        now_utc = datetime.now(timezone.utc)
        if not analysis:
            analysis = ArticleAnalysis(
                id=uuid.uuid4(),
                article_id=article.id,
                analysis_version=self.analysis_version,
                analysis_status="PROCESSING",
                analysis_attempts=1,
            )
            self.session.add(analysis)
            article.analysis = analysis
        else:
            analysis.analysis_status = "PROCESSING"
            analysis.analysis_attempts += 1
            analysis.analysis_version = self.analysis_version

        await self.session.commit()

        # 3. Prepare input content (clean, structured, character-bounded)
        max_chars = getattr(settings, "MAX_ANALYSIS_CHARS", 12000)
        body_content = (article.content or "")[:max_chars]
        description = article.description or ""
        title = article.title

        try:
            # 4. Call AI Analyzer (Provider abstraction)
            ai_output: ArticleAnalysisOutput = await self.analyzer.analyze_article(
                title=title,
                description=description,
                content=body_content,
            )

            # 5. Resolve & Link Topics in database with confidence
            resolved_topics = await self.topic_classifier.resolve_and_link_topics(
                article_id=article.id,
                extracted_topics=ai_output.topics,
                create_missing=True,
            )

            # 6. Resolve & Link Entities in database with confidence
            resolved_entities = await self.entity_resolver.resolve_and_link_entities(
                article_id=article.id,
                extracted_entities=ai_output.entities,
            )

            # 7. Store Keywords with weights
            # Clear previous keywords
            del_kw = select(ArticleKeyword).where(ArticleKeyword.article_id == article.id)
            kw_res = await self.session.execute(del_kw)
            for old_kw in kw_res.scalars().all():
                await self.session.delete(old_kw)

            created_keywords = []
            for kw_item in ai_output.keywords:
                kw_obj = ArticleKeyword(
                    id=uuid.uuid4(),
                    article_id=article.id,
                    keyword=kw_item.keyword,
                    weight=kw_item.weight,
                )
                self.session.add(kw_obj)
                created_keywords.append(kw_obj)

            # 8. Generate Semantic Vector Embedding
            topic_names = [t.name for t, _ in resolved_topics]
            keyword_names = [k.keyword for k in created_keywords]
            embedding_vector, emb_model, emb_time = await self.embedding_service.generate_article_embedding(
                title=title,
                description=description,
                summary=ai_output.summary,
                topics=topic_names,
                keywords=keyword_names,
                body=body_content,
            )

            # 9. Update ArticleAnalysis Record
            analysis.primary_category = ai_output.primary_category.value
            analysis.article_type = ai_output.article_type.value
            analysis.importance_score = ai_output.importance_score
            analysis.summary = ai_output.summary
            analysis.language = ai_output.language
            analysis.analysis_status = "SUCCESS"
            analysis.analysis_error = None
            analysis.analyzed_at = datetime.now(timezone.utc)

            if embedding_vector is not None:
                analysis.embedding = embedding_vector
                analysis.embedding_model = emb_model
                analysis.embedding_version = self.analysis_version
                analysis.embedded_at = emb_time

            # Update language on Article entity if detected
            if ai_output.language:
                article.language = ai_output.language

            await self.session.commit()

            duration = round(time.time() - start_time, 3)
            logger.info(
                f"Article analysis completed for {article.id} ({article.title[:40]}...) in {duration}s. "
                f"Cat: {analysis.primary_category}, Topics: {len(resolved_topics)}, Entities: {len(resolved_entities)}"
            )

            return {
                "article_id": str(article.id),
                "status": "SUCCESS",
                "primary_category": analysis.primary_category,
                "article_type": analysis.article_type,
                "importance_score": analysis.importance_score,
                "summary": analysis.summary,
                "language": analysis.language,
                "topics": [{"name": t.name, "slug": t.slug, "confidence": conf} for t, conf in resolved_topics],
                "entities": [{"name": e.name, "type": e.entity_type, "confidence": conf} for e, conf in resolved_entities],
                "keywords": [{"keyword": k.keyword, "weight": k.weight} for k in created_keywords],
                "has_embedding": analysis.embedding is not None,
                "analysis_version": analysis.analysis_version,
                "duration_seconds": duration,
            }

        except Exception as exc:
            logger.error(f"Article analysis failed for {article.id}: {exc}", exc_info=True)
            analysis.analysis_status = "FAILED"
            analysis.analysis_error = str(exc)
            await self.session.commit()

            return {
                "article_id": str(article.id),
                "status": "FAILED",
                "error": str(exc),
            }

    async def analyze_pending_articles(
        self,
        limit: int = 20,
        concurrency: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Batch analyze articles that have not yet been analyzed or previously failed.
        
        Args:
            limit: Maximum articles to process in this batch.
            concurrency: Number of concurrent analysis tasks (default settings.ANALYSIS_CONCURRENCY).
        """
        max_concurrency = concurrency or getattr(settings, "ANALYSIS_CONCURRENCY", 3)
        sem = asyncio.Semaphore(max_concurrency)

        # Query candidates: articles without analysis or where analysis_status != 'SUCCESS'
        stmt = (
            select(Article.id)
            .outerjoin(ArticleAnalysis, Article.id == ArticleAnalysis.article_id)
            .where(
                or_(
                    ArticleAnalysis.id.is_(None),
                    ArticleAnalysis.analysis_status == "NOT_ANALYZED",
                    ArticleAnalysis.analysis_status == "PENDING",
                    ArticleAnalysis.analysis_status == "FAILED",
                )
            )
            .order_by(Article.published_at.desc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        article_ids = list(res.scalars().all())

        if not article_ids:
            return {
                "processed": 0,
                "successful": 0,
                "failed": 0,
                "results": [],
            }

        results: List[Dict[str, Any]] = []
        counts = {"successful": 0, "failed": 0}

        async def _worker(aid: uuid.UUID) -> None:
            async with sem:
                try:
                    res_dict = await self.analyze_article(aid)
                    if res_dict.get("status") == "SUCCESS":
                        counts["successful"] += 1
                    else:
                        counts["failed"] += 1
                    results.append(res_dict)
                except Exception as e:
                    logger.error(f"Error in batch analysis worker for {aid}: {e}")
                    counts["failed"] += 1
                    results.append({"article_id": str(aid), "status": "FAILED", "error": str(e)})

        tasks = [_worker(aid) for aid in article_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

        return {
            "processed": len(article_ids),
            "successful": counts["successful"],
            "failed": counts["failed"],
            "results": results,
        }
