"""keyword_scorer.py — Article Keyword Relevance Scorer.

Evaluates semantic and normalized token overlap between article keywords and user interest terms.
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple


class KeywordScorer:
    """Evaluates article keywords against user interest topic terms."""

    # Term expansion synonyms for common domains
    SYNONYM_MAP: Dict[str, Set[str]] = {
        "ai": {"llm", "gpt", "model", "neural", "deep", "machine", "agent", "transformer"},
        "artificial-intelligence": {"ai", "llm", "machine", "learning", "neural", "vision", "nlp"},
        "machine-learning": {"ml", "model", "training", "dataset", "deep", "neural", "algorithm"},
        "programming": {"python", "code", "coding", "developer", "software", "api", "framework", "rust", "javascript"},
        "startups": {"founder", "venture", "funding", "seed", "unicorn", "investor", "valuation"},
        "markets-economy": {"stock", "stocks", "market", "inflation", "revenue", "fed", "yield", "trade"},
        "finance": {"banking", "crypto", "bitcoin", "dividend", "bonds", "forex", "treasury"},
        "space-astronomy": {"orbit", "planet", "telescope", "star", "galaxy", "rocket", "lunar", "mars"},
    }

    @classmethod
    def _extract_keywords(cls, article_keywords: Any) -> List[Tuple[str, float]]:
        """Normalize keywords to list of (keyword_str, weight)."""
        result = []
        if not article_keywords:
            return result

        for k in article_keywords:
            if hasattr(k, "keyword"):
                kw = str(k.keyword).lower().strip()
                weight = float(getattr(k, "weight", 1.0) or 1.0)
                result.append((kw, weight))
            elif isinstance(k, dict):
                kw = str(k.get("keyword") or "").lower().strip()
                weight = float(k.get("weight", 1.0))
                result.append((kw, weight))
            elif isinstance(k, tuple) or isinstance(k, list):
                kw = str(k[0]).lower().strip()
                weight = float(k[1]) if len(k) > 1 else 1.0
                result.append((kw, weight))
            elif isinstance(k, str):
                result.append((k.lower().strip(), 1.0))
        return result

    @classmethod
    def score_keywords(
        cls,
        article_keywords: Any,
        positive_interests: Dict[str, float],
        positive_topic_names: Optional[List[str]] = None,
        default_neutral_score: float = 0.5,
    ) -> float:
        """Compute keyword relevance score in [0.0, 1.0]."""
        if not positive_interests:
            return default_neutral_score

        keywords = cls._extract_keywords(article_keywords)
        if not keywords:
            return default_neutral_score

        # Build set of user interest tokens & slugs
        user_terms: Dict[str, float] = {}
        for slug, score in positive_interests.items():
            user_terms[slug.lower()] = score
            for token in re.split(r"[-_\s]+", slug.lower()):
                if len(token) >= 3:
                    user_terms[token] = max(user_terms.get(token, 0.0), score)

        if positive_topic_names:
            for name in positive_topic_names:
                for token in re.split(r"[-_\s]+", name.lower()):
                    if len(token) >= 3:
                        user_terms[token] = max(user_terms.get(token, 0.0), 0.8)

        # Match keywords against user terms and expansions
        matched_scores: List[float] = []

        for kw, kw_weight in keywords:
            kw_tokens = set(re.split(r"[-_\s]+", kw))
            best_match = 0.0

            for term, term_score in user_terms.items():
                if term in kw or kw in term or any(t == term for t in kw_tokens):
                    match_val = kw_weight * term_score
                    if match_val > best_match:
                        best_match = match_val

                # Check synonym expansion
                synonyms = cls.SYNONYM_MAP.get(term, set())
                if any(syn in kw_tokens or syn in kw for syn in synonyms):
                    match_val = kw_weight * term_score * 0.85
                    if match_val > best_match:
                        best_match = match_val

            if best_match > 0.0:
                matched_scores.append(best_match)

        if not matched_scores:
            return 0.40  # Low baseline if keywords exist but none match user interest

        top_score = max(matched_scores)
        additional = sum(matched_scores[1:]) * 0.1
        final_kw_score = min(1.0, top_score + additional)
        return round(max(0.0, min(1.0, final_kw_score)), 4)
