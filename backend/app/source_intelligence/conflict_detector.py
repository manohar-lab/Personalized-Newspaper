"""conflict_detector.py — Discrepancy & contrasting coverage detection in story clusters."""
import re
from typing import Any, List, Optional, Tuple


class ConflictDetector:
    """
    Detects potential claim differences or conflicting reports across articles in a story cluster.
    CRITICAL PRINCIPLE: Never claims one source is factually FALSE; flags POTENTIAL_CONFLICT
    for balanced multi-perspective presentation.
    """

    OPPOSING_PAIRS = [
        ({"launch", "launches", "launched", "launching", "scheduled", "begins", "starts", "proceeding", "on track"}, {"delay", "delays", "delayed", "delaying", "postpone", "postponed", "cancelled", "halted", "suspended"}),
        ({"approve", "approved", "approves", "approving", "passes", "cleared", "wins"}, {"reject", "rejected", "rejects", "fails", "denied", "blocked"}),
        ({"rise", "rises", "gain", "gains", "surges", "up", "record"}, {"fall", "falls", "drop", "drops", "plunges", "down", "slump"}),
        ({"confirms", "confirmed", "confirming", "admits"}, {"denies", "denied", "denying", "refutes", "dismisses"}),
        ({"acquires", "buys", "merges"}, {"cancels deal", "walks away", "rejects buyout"}),
        ({"resigns", "steps down", "quits"}, {"stays", "denies resignation"}),
    ]


    @classmethod
    def _extract_words(cls, text: str) -> set:
        return set(re.findall(r"\b[a-zA-Z]{3,}\b", (text or "").lower()))

    @classmethod
    def detect_conflicts_in_cluster(
        cls,
        articles: List[Any],
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Analyzes articles covering the same story cluster for contrasting claims.
        Returns:
            (has_conflict: bool, conflict_summary: Optional[str], conflict_flag: Optional[str])
        """
        if len(articles) < 2:
            return False, None, None

        article_wordsets = [
            cls._extract_words(f"{getattr(a, 'title', '')} {getattr(a, 'description', '')}")
            for a in articles
        ]

        for i in range(len(article_wordsets)):
            for j in range(i + 1, len(article_wordsets)):
                words_a = article_wordsets[i]
                words_b = article_wordsets[j]

                for positive_set, contrasting_set in cls.OPPOSING_PAIRS:
                    a_has_pos = bool(words_a & positive_set)
                    b_has_neg = bool(words_b & contrasting_set)
                    a_has_neg = bool(words_a & contrasting_set)
                    b_has_pos = bool(words_b & positive_set)

                    if (a_has_pos and b_has_neg) or (a_has_neg and b_has_pos):
                        src_a = getattr(articles[i], "source_name", "Source A")
                        src_b = getattr(articles[j], "source_name", "Source B")
                        summary = f"Different reports detected between {src_a} and {src_b}."
                        return True, summary, "POTENTIAL_CONFLICT"

        return False, None, None
