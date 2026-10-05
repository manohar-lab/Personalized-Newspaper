"""gemini_provider.py — Phase 7 Google Gemini AI Provider Implementation.

Supports structured JSON outputs using Google Gemini REST API.
"""
import json
import logging
from typing import List, Optional

import httpx

from app.ai.base import ArticleAnalyzer, EmbeddingProvider
from app.ai.classification.prompts import (
    ARTICLE_ANALYSIS_SYSTEM_PROMPT,
    build_article_analysis_user_prompt,
)
from app.ai.classification.schemas import ArticleAnalysisOutput
from app.core.config import settings

logger = logging.getLogger(__name__)


class GeminiArticleAnalyzer(ArticleAnalyzer):
    """Google Gemini implementation of ArticleAnalyzer."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or settings.AI_API_KEY
        self.model = model or settings.AI_MODEL or "gemini-1.5-flash"

    async def analyze_article(
        self,
        title: str,
        description: Optional[str] = None,
        content: Optional[str] = None,
    ) -> ArticleAnalysisOutput:
        if not self.api_key:
            raise ValueError("Gemini API key not configured")

        user_content = build_article_analysis_user_prompt(title, description or "", content or "")
        max_chars = getattr(settings, "MAX_ANALYSIS_CHARS", 12000)
        if len(user_content) > max_chars:
            user_content = user_content[:max_chars] + "\n...[truncated for length]"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {
                "parts": [{"text": ARTICLE_ANALYSIS_SYSTEM_PROMPT}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_content}]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.1,
            }
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        candidate_text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed_dict = json.loads(candidate_text)
        return ArticleAnalysisOutput(**parsed_dict)
