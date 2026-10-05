"""query_parser.py — Phase 11 Deterministic Search Query Parser."""
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
    "cybersecurity": "Cybersecurity",
    "security": "Cybersecurity",
    "technology": "Technology",
    "tech": "Technology",
    "science": "Science",
    "space": "Science",
    "finance": "Business",
    "business": "Business",
    "economy": "Business",
    "markets": "Business",
    "health": "Health",
    "medicine": "Health",
    "sports": "Sports",
    "entertainment": "Entertainment",
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
]


class QueryParser:
    """
    Parses natural language search queries into structured search signals:
    - Clean search keywords
    - Detected topic tags
    - Detected entity tags
    - Inferred date filters
    """

    @classmethod
    def parse_query(cls, raw_query: str) -> Tuple[ParsedQueryInfo, Optional[datetime], Optional[datetime]]:
        """
        Parses query and returns (ParsedQueryInfo, date_from, date_to).
        """
        if not raw_query or not raw_query.strip():
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

        text = raw_query.strip()
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
            (r"\b(this week|past week|last 7 days)\b", "last_7_days", now - timedelta(days=7), None),
            (r"\b(this month|past month|last 30 days)\b", "last_30_days", now - timedelta(days=30), None),
            (r"\b(past 24 hours|last 24 hours)\b", "last_24_hours", now - timedelta(hours=24), None),
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
        for phrase, canonical_topic in KNOWN_TOPIC_SYNONYMS.items():
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

        # 4. Clean keywords
        clean_text = re.sub(r"\s+", " ", text).strip()

        parsed_info = ParsedQueryInfo(
            raw_query=raw_query,
            clean_keywords=clean_text or raw_query.strip(),
            detected_topics=detected_topics,
            detected_entities=detected_entities,
            detected_sources=[],
            date_range_detected=date_label,
        )

        return parsed_info, date_from, date_to
