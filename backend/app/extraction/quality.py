"""quality.py — Phase 20 Article Extraction Quality Scoring.

Evaluates extracted article content across length, headline, structure, author,
date, and metadata dimensions to generate an extraction_quality_score (0.0 to 1.0).
"""
import re
from typing import List, Optional
from app.extraction.models import ExtractedArticleData, ExtractionQualityBreakdown


class ArticleQualityScorer:
    """Evaluates the extraction quality and completeness of an article."""

    @staticmethod
    def evaluate(article: ExtractedArticleData) -> ExtractionQualityBreakdown:
        """Compute multidimensional quality breakdown and composite score."""
        flags: List[str] = []

        # 1. Content Length Score (0.0 - 1.0)
        content = (article.content or "").strip()
        char_len = len(content)
        word_count = len(content.split())

        if char_len >= 800 or word_count >= 150:
            length_score = 1.0
        elif char_len >= 400 or word_count >= 70:
            length_score = 0.85
        elif char_len >= 200 or word_count >= 35:
            length_score = 0.70
        elif char_len >= 100 or word_count >= 20:
            length_score = 0.45
        else:
            length_score = 0.0
            flags.append("VERY_SHORT_BODY")

        # 2. Headline Score (0.0 - 1.0)
        title = (article.title or article.headline or "").strip()
        if not title:
            headline_score = 0.0
            flags.append("MISSING_TITLE")
        elif len(title) < 8:
            headline_score = 0.3
            flags.append("SHORT_TITLE")
        elif len(title) > 250:
            headline_score = 0.6
        else:
            headline_score = 1.0

        # 3. Metadata Score (0.0 - 1.0)
        meta_score = 0.0
        if article.description and len(article.description.strip()) > 15:
            meta_score += 0.5
        if article.image_url and article.image_url.startswith(("http://", "https://")):
            meta_score += 0.5
        if not article.description and not article.image_url:
            flags.append("LOW_METADATA")

        # 4. Date Score (0.0 - 1.0)
        if article.publication_date is not None:
            date_score = 1.0
        else:
            date_score = 0.2
            flags.append("MISSING_DATE")

        # 5. Author Score (0.0 - 1.0)
        if article.author and len(article.author.strip()) > 1:
            author_score = 1.0
        else:
            author_score = 0.25
            flags.append("MISSING_AUTHOR")

        # 6. Structure Score (0.0 - 1.0)
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        if len(paragraphs) >= 3:
            structure_score = 1.0
        elif len(paragraphs) == 2:
            structure_score = 0.75
        elif len(paragraphs) == 1 and len(content) > 200:
            structure_score = 0.5
        else:
            structure_score = 0.2
            flags.append("POOR_PARAGRAPH_STRUCTURE")

        # Composite Overall Quality Score
        overall = (
            0.35 * length_score
            + 0.20 * headline_score
            + 0.15 * structure_score
            + 0.10 * date_score
            + 0.10 * author_score
            + 0.10 * meta_score
        )
        overall = round(max(0.0, min(1.0, overall)), 3)

        # Acceptability threshold
        is_acceptable = overall >= 0.35 and length_score > 0.0 and headline_score > 0.0

        return ExtractionQualityBreakdown(
            content_length_score=round(length_score, 2),
            headline_score=round(headline_score, 2),
            metadata_score=round(meta_score, 2),
            date_score=round(date_score, 2),
            author_score=round(author_score, 2),
            structure_score=round(structure_score, 2),
            overall_score=overall,
            is_acceptable=is_acceptable,
            flags=flags,
        )
