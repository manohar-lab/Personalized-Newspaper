"""mock_provider.py — Phase 7 Deterministic Mock AI Provider.

Provides zero-cost, fast, reliable, and deterministic analysis and embeddings
for testing, CI/CD, and local offline development.
"""
import hashlib
import re
from typing import List, Optional

from app.ai.base import ArticleAnalyzer, EmbeddingProvider
from app.ai.classification.schemas import (
    ArticleAnalysisOutput,
    ArticleType,
    EntityExtractionItem,
    EntityType,
    KeywordExtractionItem,
    PrimaryCategory,
    TopicExtractionItem,
)


class MockArticleAnalyzer(ArticleAnalyzer):
    """Deterministic heuristic analyzer for testing and offline environments."""

    CATEGORY_KEYWORDS = {
        PrimaryCategory.TECHNOLOGY: [
            "ai", "software", "computing", "chip", "semiconductor", "cloud",
            "coding", "developer", "robot", "apple", "google", "microsoft",
            "nvidia", "meta", "intel", "quantum", "algorithm", "python",
        ],
        PrimaryCategory.SCIENCE: [
            "space", "nasa", "physics", "telescope", "fusion", "planet",
            "exoplanet", "biology", "genetics", "chemistry", "orbit", "astronomy",
        ],
        PrimaryCategory.BUSINESS: [
            "market", "revenue", "startup", "economy", "stock", "growth",
            "ceo", "merger", "acquisition", "industry", "trade", "investment",
        ],
        PrimaryCategory.FINANCE: [
            "inflation", "banking", "interest rate", "fed", "crypto", "bitcoin",
            "dividend", "bonds", "forex", "treasury",
        ],
        PrimaryCategory.HEALTH: [
            "medical", "health", "vaccine", "disease", "clinical", "hospital",
            "doctor", "therapy", "fda", "cancer", "pharma",
        ],
        PrimaryCategory.POLITICS: [
            "government", "election", "senate", "parliament", "congress",
            "president", "minister", "legislation", "treaty", "policy",
        ],
        PrimaryCategory.WORLD: [
            "international", "un", "global", "summit", "nation", "diplomacy",
            "treaty", "europe", "asia", "africa",
        ],
        PrimaryCategory.ENTERTAINMENT: [
            "movie", "film", "music", "hollywood", "actor", "game", "gaming",
            "cinema", "concert", "album",
        ],
        PrimaryCategory.SPORTS: [
            "football", "cricket", "basketball", "olympics", "championship",
            "match", "league", "tournament", "player", "coach",
        ],
    }

    KNOWN_ENTITIES = [
        ("NASA", EntityType.ORGANIZATION),
        ("OpenAI", EntityType.COMPANY),
        ("Google", EntityType.COMPANY),
        ("Microsoft", EntityType.COMPANY),
        ("NVIDIA", EntityType.COMPANY),
        ("Apple", EntityType.COMPANY),
        ("Amazon", EntityType.COMPANY),
        ("Meta", EntityType.COMPANY),
        ("Python", EntityType.TECHNOLOGY),
        ("Linux", EntityType.TECHNOLOGY),
        ("United States", EntityType.LOCATION),
        ("European Union", EntityType.LOCATION),
    ]

    async def analyze_article(
        self,
        title: str,
        description: Optional[str] = None,
        content: Optional[str] = None,
    ) -> ArticleAnalysisOutput:
        full_text = f"{title} {description or ''} {content or ''}".lower()

        # 1. Determine Category
        matched_category = PrimaryCategory.TECHNOLOGY
        max_matches = 0
        for cat, keywords in self.CATEGORY_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in full_text)
            if matches > max_matches:
                max_matches = matches
                matched_category = cat

        # 2. Determine Article Type
        art_type = ArticleType.NEWS
        if any(w in full_text for w in ("tutorial", "how to", "guide", "walkthrough")):
            art_type = ArticleType.TUTORIAL
        elif any(w in full_text for w in ("opinion", "column", "editorial", "perspective")):
            art_type = ArticleType.OPINION
        elif any(w in full_text for w in ("research", "study", "paper", "experiment")):
            art_type = ArticleType.RESEARCH
        elif any(w in full_text for w in ("announcement", "announces", "launched", "unveils")):
            art_type = ArticleType.ANNOUNCEMENT
        elif any(w in full_text for w in ("analysis", "deep dive", "breakdown", "outlook")):
            art_type = ArticleType.ANALYSIS

        # 3. Determine Importance Score
        importance = 0.65
        if any(w in full_text for w in ("breakthrough", "historic", "milestone", "revolutionary", "crisis")):
            importance = 0.90
        elif any(w in full_text for w in ("minor", "routine", "weekly", "brief", "patch")):
            importance = 0.35

        # 4. Generate Summary
        if description and len(description.strip()) > 30:
            summary = description.strip()
        elif content and len(content.strip()) > 50:
            sentences = re.split(r"(?<=[.!?])\s+", content.strip())
            summary = " ".join(sentences[:3])
        else:
            summary = f"{title}. Full details are covered in the original report."

        # 5. Extract Topics
        topics = []
        if matched_category == PrimaryCategory.TECHNOLOGY:
            topics.append(TopicExtractionItem(name="Artificial Intelligence", confidence=0.92))
            topics.append(TopicExtractionItem(name="Software Engineering", confidence=0.85))
        elif matched_category == PrimaryCategory.SCIENCE:
            topics.append(TopicExtractionItem(name="Space & Astronomy", confidence=0.94))
            topics.append(TopicExtractionItem(name="Physics", confidence=0.88))
        elif matched_category == PrimaryCategory.BUSINESS:
            topics.append(TopicExtractionItem(name="Markets & Economy", confidence=0.90))
            topics.append(TopicExtractionItem(name="Startups", confidence=0.80))
        else:
            topics.append(TopicExtractionItem(name=matched_category.value.title(), confidence=0.85))

        # 6. Extract Entities
        entities = []
        for name, etype in self.KNOWN_ENTITIES:
            if re.search(r"\b" + re.escape(name) + r"\b", f"{title} {description or ''} {content or ''}", re.I):
                entities.append(EntityExtractionItem(name=name, type=etype, confidence=0.95))

        if not entities:
            # Add fallback technology entity if applicable
            if "ai" in full_text:
                entities.append(EntityExtractionItem(name="Artificial Intelligence", type=EntityType.TECHNOLOGY, confidence=0.90))

        # 7. Extract Keywords
        words = re.findall(r"\b[a-zA-Z]{4,15}\b", full_text)
        stopwords = {"this", "that", "with", "from", "have", "more", "will", "been", "were", "they", "their", "about", "which"}
        filtered = [w for w in words if w not in stopwords]
        freq = {}
        for w in filtered:
            freq[w] = freq.get(w, 0) + 1
        sorted_kw = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:6]
        keywords = [
            KeywordExtractionItem(keyword=kw, weight=round(min(1.0, 0.6 + count * 0.1), 2))
            for kw, count in sorted_kw
        ]
        if not keywords:
            keywords = [KeywordExtractionItem(keyword="news", weight=0.8)]

        return ArticleAnalysisOutput(
            primary_category=matched_category,
            article_type=art_type,
            importance_score=importance,
            language="en",
            summary=summary,
            topics=topics,
            entities=entities,
            keywords=keywords,
        )


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic hash-based embedding generator for testing."""

    @property
    def model_name(self) -> str:
        return "mock-embedding-v1"

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        if not text:
            return None
        # Generate 64-dimensional normalized float vector from sha256
        h = hashlib.sha256(text.encode("utf-8")).digest()
        # 32 bytes -> expand to 64 floats
        vector = []
        for b in h:
            vector.append(round((b - 128) / 128.0, 4))
            vector.append(round(((b * 7) % 256 - 128) / 128.0, 4))
        return vector[:64]
