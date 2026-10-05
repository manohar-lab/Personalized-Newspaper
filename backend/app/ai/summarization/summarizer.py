"""summarizer.py — Phase 7 Article Summarization Service.

Provides validation, trimming, and fallback mechanics for 2–4 sentence factual summaries.
"""
import re
from typing import Optional


class ArticleSummarizer:
    """Manages summary formatting and fallback extraction."""

    @staticmethod
    def format_summary(summary_text: str, max_sentences: int = 4) -> str:
        """Ensure summary is clean, neutral, and within standard sentence length."""
        if not summary_text:
            return ""

        cleaned = summary_text.strip()
        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", cleaned)
        if len(sentences) > max_sentences:
            return " ".join(sentences[:max_sentences])
        return cleaned

    @staticmethod
    def fallback_summary(title: str, description: Optional[str] = None, content: Optional[str] = None) -> str:
        """Deterministic fallback summary when LLM generation is bypassed."""
        if description and len(description.strip()) > 30:
            return ArticleSummarizer.format_summary(description.strip())
        if content and len(content.strip()) > 50:
            sentences = re.split(r"(?<=[.!?])\s+", content.strip())
            return " ".join(sentences[:3])
        return f"{title}. Details available in the full report."
