"""explanations.py — Recommendation Explanation Generator."""
from typing import Optional, Dict, Any


class ExplanationGenerator:
    """Generates human-readable, context-aware recommendation explanations without exposing raw scores."""

    @staticmethod
    def generate_explanation(
        reason_type: str,
        topic_name: Optional[str] = None,
        entity_name: Optional[str] = None,
        source_article_title: Optional[str] = None,
    ) -> Dict[str, str]:
        """Derive reason_type and reason_text for display in the frontend."""
        rtype = (reason_type or "STRONG_INTEREST").upper().strip()

        if rtype == "SIMILAR_ARTICLE" and source_article_title:
            truncated = (source_article_title[:45] + "...") if len(source_article_title) > 48 else source_article_title
            return {
                "reason_type": "SIMILAR_ARTICLE",
                "reason_text": f"Similar to '{truncated}'",
            }
        elif rtype == "EMERGING_INTEREST":
            t_str = f" in {topic_name}" if topic_name else ""
            return {
                "reason_type": "EMERGING_INTEREST",
                "reason_text": f"From a topic you've recently started exploring{t_str}",
            }
        elif rtype == "TRENDING_FOR_YOU":
            t_str = f" in {topic_name}" if topic_name else ""
            return {
                "reason_type": "TRENDING_FOR_YOU",
                "reason_text": f"Popular and trending{t_str}",
            }
        elif rtype == "DISCOVERY":
            t_str = f" in {topic_name}" if topic_name else ""
            return {
                "reason_type": "DISCOVERY",
                "reason_text": f"Discover something new{t_str}",
            }
        elif rtype == "RELATED_TO_READING":
            if entity_name:
                return {
                    "reason_type": "RELATED_TO_READING",
                    "reason_text": f"Because you frequently read about {entity_name}",
                }
            elif topic_name:
                return {
                    "reason_type": "RELATED_TO_READING",
                    "reason_text": f"Related to your reading on {topic_name}",
                }
            return {
                "reason_type": "RELATED_TO_READING",
                "reason_text": "Based on your recent reading history",
            }
        else:  # STRONG_INTEREST fallback
            if topic_name:
                return {
                    "reason_type": "STRONG_INTEREST",
                    "reason_text": f"Because of your strong interest in {topic_name}",
                }
            elif entity_name:
                return {
                    "reason_type": "STRONG_INTEREST",
                    "reason_text": f"Matching your interest in {entity_name}",
                }
            return {
                "reason_type": "STRONG_INTEREST",
                "reason_text": "Matches your personalized reading preferences",
            }
