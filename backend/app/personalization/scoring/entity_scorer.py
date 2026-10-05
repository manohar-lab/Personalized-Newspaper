"""entity_scorer.py — Entity Relevance Scorer.

Compares extracted article entities (companies, organizations, technologies, locations)
against user interest topics and associated domain signals.
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple


class EntityScorer:
    """Evaluates relevance of article entities with respect to user topic profile."""

    # Curated knowledge associations between high-frequency entities and canonical topic keywords
    ENTITY_TOPIC_ASSOCIATIONS: Dict[str, List[str]] = {
        "openai": ["artificial-intelligence", "machine-learning", "technology", "software"],
        "nvidia": ["artificial-intelligence", "machine-learning", "technology", "chips", "hardware"],
        "google": ["technology", "artificial-intelligence", "cloud", "software"],
        "microsoft": ["technology", "software", "cloud", "artificial-intelligence"],
        "apple": ["technology", "hardware", "software", "mobile"],
        "meta": ["technology", "social-media", "virtual-reality", "artificial-intelligence"],
        "amazon": ["technology", "cloud", "business", "e-commerce"],
        "python": ["programming", "software-engineering", "data-science", "artificial-intelligence"],
        "linux": ["programming", "open-source", "software-engineering", "operating-systems"],
        "nasa": ["space-astronomy", "science", "physics", "exploration"],
        "spacex": ["space-astronomy", "science", "aerospace", "technology"],
        "european union": ["politics", "world-news", "diplomacy", "international"],
        "united states": ["politics", "world-news", "diplomacy"],
        "federal reserve": ["finance", "markets-economy", "banking", "economics"],
        "wall street": ["finance", "markets-economy", "stocks", "business"],
    }

    @classmethod
    def _extract_entities(cls, article_entities: Any) -> List[Tuple[str, str, float]]:
        """Normalize article entities into list of (normalized_name, entity_type, confidence)."""
        result = []
        if not article_entities:
            return result

        for e in article_entities:
            if hasattr(e, "normalized_name") and hasattr(e, "confidence"):
                name = str(e.normalized_name).lower().strip()
                etype = str(getattr(e, "entity_type", "OTHER")).upper()
                conf = float(e.confidence or 1.0)
                result.append((name, etype, conf))
            elif hasattr(e, "name"):
                name = str(e.name).lower().strip()
                etype = str(getattr(e, "entity_type", "OTHER")).upper()
                conf = float(getattr(e, "confidence", 1.0) or 1.0)
                result.append((name, etype, conf))
            elif isinstance(e, dict):
                name = str(e.get("name") or e.get("normalized_name") or "").lower().strip()
                etype = str(e.get("entity_type", "OTHER")).upper()
                conf = float(e.get("confidence", 1.0))
                result.append((name, etype, conf))
            elif isinstance(e, tuple) or isinstance(e, list):
                name = str(e[0]).lower().strip()
                etype = str(e[1]).upper() if len(e) > 1 and isinstance(e[1], str) else "OTHER"
                conf = float(e[2]) if len(e) > 2 else (float(e[1]) if len(e) > 1 and isinstance(e[1], (int, float)) else 1.0)
                result.append((name, etype, conf))
            elif isinstance(e, str):
                result.append((e.lower().strip(), "OTHER", 1.0))
        return result

    @classmethod
    def score_entities(
        cls,
        article_entities: Any,
        positive_interests: Dict[str, float],
        positive_topic_names: Optional[List[str]] = None,
        default_neutral_score: float = 0.5,
    ) -> float:
        """Compute entity relevance score in [0.0, 1.0].
        
        If no user interests or no entities, returns default neutral score.
        """
        if not positive_interests:
            return default_neutral_score

        entities = cls._extract_entities(article_entities)
        if not entities:
            return default_neutral_score

        user_topics_set = set(k.lower() for k in positive_interests.keys())
        if positive_topic_names:
            for name in positive_topic_names:
                user_topics_set.add(name.lower())

        matches: List[float] = []

        for entity_name, entity_type, confidence in entities:
            # 1. Direct name match with user topic (e.g. topic "Python" vs entity "Python")
            direct_match = False
            for ut in user_topics_set:
                if ut in entity_name or entity_name in ut:
                    user_weight = max((v for k, v in positive_interests.items() if k in ut or ut in k), default=0.8)
                    matches.append(confidence * user_weight)
                    direct_match = True
                    break

            if direct_match:
                continue

            # 2. Association lookup
            assoc_topics = cls.ENTITY_TOPIC_ASSOCIATIONS.get(entity_name, [])
            for assoc in assoc_topics:
                for ut in user_topics_set:
                    slug_cleaned = re.sub(r"[^a-z0-9]", "", ut)
                    assoc_cleaned = re.sub(r"[^a-z0-9]", "", assoc)
                    if slug_cleaned in assoc_cleaned or assoc_cleaned in slug_cleaned:
                        user_weight = max((v for k, v in positive_interests.items() if k in ut or ut in k), default=0.8)
                        matches.append(confidence * user_weight * 0.9)
                        break

        if not matches:
            # If entities are present but none matched user topics, slight attenuation from neutral
            return 0.45

        # Aggregate entity relevance
        base_match = max(matches)
        bonus = sum(matches[1:]) * 0.1
        score = min(1.0, base_match + bonus)
        return round(max(0.0, min(1.0, score)), 4)
