"""openai_provider.py — Phase 7 OpenAI AI Provider Implementation.

Supports structured JSON outputs with chat completions and vector embeddings.
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


class OpenAIArticleAnalyzer(ArticleAnalyzer):
    """OpenAI implementation of ArticleAnalyzer."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or settings.AI_API_KEY
        self.model = model or settings.AI_MODEL or "gpt-4o-mini"
        self.base_url = base_url or settings.AI_API_BASE_URL or "https://api.openai.com/v1"

    async def analyze_article(
        self,
        title: str,
        description: Optional[str] = None,
        content: Optional[str] = None,
    ) -> ArticleAnalysisOutput:
        if not self.api_key:
            raise ValueError("OpenAI API key not configured")

        user_content = build_article_analysis_user_prompt(title, description or "", content or "")
        # Enforce max chars limit
        max_chars = getattr(settings, "MAX_ANALYSIS_CHARS", 12000)
        if len(user_content) > max_chars:
            user_content = user_content[:max_chars] + "\n...[truncated for length]"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": ARTICLE_ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        raw_json_str = data["choices"][0]["message"]["content"]
        parsed_dict = json.loads(raw_json_str)

        # Validate with Pydantic
        return ArticleAnalysisOutput(**parsed_dict)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI implementation of EmbeddingProvider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or settings.AI_API_KEY
        self._model = model or settings.EMBEDDING_MODEL or "text-embedding-3-small"
        self.base_url = base_url or settings.AI_API_BASE_URL or "https://api.openai.com/v1"

    @property
    def model_name(self) -> str:
        return self._model

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        if not self.api_key or not text:
            return None

        # Truncate text to ~8000 tokens / 30000 chars
        truncated = text[:30000]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "input": truncated,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{self.base_url}/embeddings", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        return data["data"][0]["embedding"]
