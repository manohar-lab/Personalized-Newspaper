"""article_versioning_service.py — Phase 20 Article Content Versioning & Change Detection.

Detects meaningful editorial updates to articles, maintains content hashes,
and notifies story intelligence when substantial updates occur.
"""
import difflib
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.extraction.url_normalizer import URLNormalizer
from app.models.article import Article

logger = logging.getLogger(__name__)


class ArticleVersioningService:
    """Detects article content modifications and coordinates story re-evaluation."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def calculate_similarity_ratio(old_text: str, new_text: str) -> float:
        """Calculate word-level similarity ratio between old and new content."""
        if not old_text and not new_text:
            return 1.0
        if not old_text or not new_text:
            return 0.0

        norm_old = URLNormalizer.normalize_text_for_comparison(old_text)
        norm_new = URLNormalizer.normalize_text_for_comparison(new_text)

        matcher = difflib.SequenceMatcher(None, norm_old.split(), norm_new.split())
        return matcher.ratio()

    @staticmethod
    def is_meaningful_update(old_text: Optional[str], new_text: Optional[str], threshold: float = 0.85) -> Tuple[bool, float]:
        """Check if difference between old and new content represents a substantive editorial update.
        
        Returns:
            (is_meaningful, similarity_ratio)
        """
        if not new_text:
            return False, 1.0
        if not old_text:
            return True, 0.0

        ratio = ArticleVersioningService.calculate_similarity_ratio(old_text, new_text)
        # If similarity is lower than threshold (e.g. < 85% similar, meaning > 15% changed)
        # or new text is significantly longer with new paragraphs
        is_meaningful = ratio < threshold or (len(new_text) - len(old_text) > 300)
        return is_meaningful, ratio

    async def check_and_apply_update(
        self,
        article: Article,
        new_content: str,
        new_title: Optional[str] = None,
        new_description: Optional[str] = None,
    ) -> bool:
        """Check if new content is a meaningful update and update article record if so.
        
        Returns True if an update was applied, False otherwise.
        """
        old_content = article.content or ""
        is_meaningful, similarity = self.is_meaningful_update(old_content, new_content)

        new_hash = hashlib.sha256(new_content.encode("utf-8")).hexdigest()

        # If hash is identical, skip
        if article.content_hash == new_hash:
            return False

        if is_meaningful:
            logger.info(
                f"Meaningful content update detected for article {article.id} "
                f"('{article.title[:40]}...'): similarity={similarity:.2f}"
            )
            # Update content hashes & timestamps
            article.content = new_content
            article.content_hash = new_hash
            article.updated_at = datetime.now(timezone.utc)
            if new_title:
                article.title = new_title
            if new_description:
                article.description = new_description

            word_count = len(new_content.split())
            article.reading_time_minutes = max(1, round(word_count / 200))

            return True

        return False
