"""base.py — Phase 7 AI Provider Abstract Base Classes.

Decouples the application logic from specific LLM vendors (OpenAI, Gemini, Local/Mock).
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from app.ai.classification.schemas import ArticleAnalysisOutput


class ArticleAnalyzer(ABC):
    """Abstract interface for AI article analysis and classification."""

    @abstractmethod
    async def analyze_article(
        self,
        title: str,
        description: Optional[str] = None,
        content: Optional[str] = None,
    ) -> ArticleAnalysisOutput:
        """Analyze article text and produce validated structured metadata."""
        pass


class EmbeddingProvider(ABC):
    """Abstract interface for vector embedding generation."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of the embedding model."""
        pass

    @abstractmethod
    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate a float embedding vector from text."""
        pass
