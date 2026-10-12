"""query_parser.py — Phase 24 Deterministic Search Query Parser & Understanding."""
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from app.search.schemas import ParsedQueryInfo


KNOWN_TOPIC_SYNONYMS: Dict[str, str] = {
    "ai": "Artificial Intelligence",
    "artificial intelligence": "Artificial Intelligence",
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
    "deep learning": "Machine Learning",
    "robotics": "Robotics",
    "cybersecurity": "Cybersecurity",
    "security": "Cybersecurity",
    "technology": "Technology",
    "tech": "Technology",
    "science": "Science",
    "space": "Science",
    "physics": "Science",
    "biology": "Science",
    "quantum": "Quantum Computing",
    "quantum computing": "Quantum Computing",
    "cloud": "Cloud Computing",
    "cloud computing": "Cloud Computing",
    "llm": "LLMs",
    "llms": "LLMs",
    "large language model": "LLMs",
    "large language models": "LLMs",
    "finance": "Business",
    "business": "Business",
    "economy": "Business",
    "markets": "Business",
    "health": "Health",
    "medicine": "Health",
    "healthcare": "Health",
    "biotech": "Health",
    "sports": "Sports",
    "entertainment": "Entertainment",
    "climate": "Science",
    "energy": "Science",
    "world": "World",
    "politics": "Politics",
}

KNOWN_ENTITIES: List[str] = [
    "OpenAI",
    "Google",
    "Microsoft",
    "Apple",
    "NVIDIA",
    "Meta",
    "Amazon",
    "Tesla",
    "Anthropic",
    "DeepMind",
    "NASA",
    "Reuters",
    "BBC",
    "CNN",
    "Bloomberg",
    "Sam Altman",
    "Jensen Huang",
    "Elon Musk",
    "Satya Nadella",
    "Sundar Pichai",
]

MAX_QUERY_LENGTH = 500


class QueryParser:
    """
    Parses natural language search queries into structured search signals:
    - Safe query normalization
    - Clean search keywords
    - Detected topic tags
    - Detected entity tags
    - Inferred date filters
    """

    @classmethod
    def normalize_query(cls, raw_query: Optional[str]) -> str:
        """
        Safely normalizes raw query text:
        - Handles None gracefully
        - Trims leading/trailing whitespace
        - Collapses repeated internal whitespace
        - Enforces reasonable query length limit
        """
        if not raw_query:
            return ""
        # Truncate to maximum allowed length
        truncated = raw_query[:MAX_QUERY_LENGTH].strip()
        # Collapse whitespace
        normalized = re.sub(r"\s+", " ", truncated)
        return normalized

    @classmethod
    def parse_query(cls, raw_query: str) -> Tuple[ParsedQueryInfo, Optional[datetime], Optional[datetime]]:
        """
        Parses query and returns (ParsedQueryInfo, date_from, date_to).
        """
        normalized = cls.normalize_query(raw_query)
        if not normalized:
            return (
                ParsedQueryInfo(
                    raw_query="",
                    clean_keywords="",
                    detected_topics=[],
                    detected_entities=[],
                    detected_sources=[],
                    date_range_detected=None,
                ),
                None,
                None,
            )

        text = normalized
        lower_text = text.lower()
        now = datetime.now(timezone.utc)
        date_from: Optional[datetime] = None
        date_to: Optional[datetime] = None
        date_label: Optional[str] = None

        # 1. Date Detection & Extraction
        date_patterns = [
            (r"\b(today)\b", "today", now.replace(hour=0, minute=0, second=0, microsecond=0), None),
            (
                r"\b(yesterday)\b",
                "yesterday",
                (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0),
                now.replace(hour=0, minute=0, second=0, microsecond=0),
            ),
            (r"\b(past 24 hours|last 24 hours|24 hours|24h)\b", "last_24_hours", now - timedelta(hours=24), None),
            (r"\b(this week|past week|last 7 days|7 days)\b", "last_7_days", now - timedelta(days=7), None),
            (r"\b(this month|past month|last 30 days|30 days)\b", "last_30_days", now - timedelta(days=30), None),
        ]

        for pattern, label, d_from, d_to in date_patterns:
            if re.search(pattern, lower_text):
                date_label = label
                date_from = d_from
                date_to = d_to
                # Remove the date phrase from keywords
                text = re.sub(pattern, "", text, flags=re.IGNORECASE)
                break

        # 2. Topic Detection
        detected_topics: List[str] = []
        # Sort synonyms by length descending so longer phrases match first
        for phrase in sorted(KNOWN_TOPIC_SYNONYMS.keys(), key=len, reverse=True):
            canonical_topic = KNOWN_TOPIC_SYNONYMS[phrase]
            pattern = rf"\b{re.escape(phrase)}\b"
            if re.search(pattern, lower_text):
                if canonical_topic not in detected_topics:
                    detected_topics.append(canonical_topic)

        # 3. Entity Detection
        detected_entities: List[str] = []
        for ent in KNOWN_ENTITIES:
            pattern = rf"\b{re.escape(ent.lower())}\b"
            if re.search(pattern, lower_text):
                if ent not in detected_entities:
                    detected_entities.append(ent)

        # 4. Clean keywords (strip extra punctuation while keeping valid alphanumeric & hyphens)
        clean_text = re.sub(r"[^\w\s\-\'\"]", " ", text)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()

        parsed_info = ParsedQueryInfo(
            raw_query=normalized,
            clean_keywords=clean_text or normalized,
            detected_topics=detected_topics,
            detected_entities=detected_entities,
            detected_sources=[],
            date_range_detected=date_label,
        )

        return parsed_info, date_from, date_to
