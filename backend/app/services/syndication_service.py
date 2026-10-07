"""syndication_service.py — Phase 20 Wire Copy & Syndication Detection.

Detects wire service syndication and reprints across multiple news outlets,
preventing duplicated confirmation inflation in story intelligence.
"""
import re
from typing import List, Optional, Set, Tuple
from app.extraction.url_normalizer import URLNormalizer


WIRE_SERVICES = [
    r"\bassociated press\b",
    r"\b\(ap\)\b",
    r"\breuters\b",
    r"\bpti\b",
    r"\bpress trust of india\b",
    r"\bbloomberg\b",
    r"\bafp\b",
    r"\bagence france-presse\b",
    r"\bupi\b",
    r"\bunited press international\b",
]


class SyndicationDetector:
    """Detects syndicated wire articles and calculates source independence."""

    @staticmethod
    def detect_wire_attribution(text: str) -> Optional[str]:
        """Check if article text or byline mentions a known wire agency."""
        if not text:
            return None
        text_lower = text.lower()
        for pattern in WIRE_SERVICES:
            if re.search(pattern, text_lower):
                # Return normalized wire agency label
                clean_name = pattern.replace(r"\b", "").replace(r"\(", "").replace(r"\)", "").upper()
                return clean_name
        return None

    @staticmethod
    def is_syndicated_copy(
        title1: str,
        title2: str,
        content1: Optional[str] = None,
        content2: Optional[str] = None,
        canonical_url1: Optional[str] = None,
        canonical_url2: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Determine if two articles are syndicated copies of the same underlying story.
        
        Returns:
            (is_syndicated, reason)
        """
        # 1. Exact canonical URL match
        if canonical_url1 and canonical_url2:
            norm1 = URLNormalizer.normalize_url(canonical_url1)
            norm2 = URLNormalizer.normalize_url(canonical_url2)
            if norm1 and norm1 == norm2:
                return True, "Identical canonical URL"

        # 2. Exact or fuzzy normalized title match (ignoring trailing wire tags like (AP), (Reuters))
        def strip_wire_suffix(t: str) -> str:
            clean = re.sub(r"(?i)\s*[\(\[\-–—\|]\s*(ap|reuters|afp|pti|bloomberg|upi|press trust of india)\s*[\)\]]?$", "", t)
            return URLNormalizer.normalize_title(clean)

        norm_t1 = strip_wire_suffix(title1)
        norm_t2 = strip_wire_suffix(title2)
        if norm_t1 and norm_t2:
            if norm_t1 == norm_t2:
                return True, "Identical normalized title after wire normalization"

            # Check word overlap in titles
            words_t1 = set(norm_t1.split())
            words_t2 = set(norm_t2.split())
            if words_t1 and words_t2:
                t_jaccard = len(words_t1 & words_t2) / len(words_t1 | words_t2)
                if t_jaccard >= 0.80:
                    return True, f"High title similarity ({t_jaccard:.2f})"

        # 3. Text fingerprint similarity
        if content1 and content2 and len(content1) > 200 and len(content2) > 200:
            words1 = set(URLNormalizer.normalize_text_for_comparison(content1[:1000]).split())
            words2 = set(URLNormalizer.normalize_text_for_comparison(content2[:1000]).split())
            if words1 and words2:
                jaccard = len(words1 & words2) / len(words1 | words2)
                if jaccard >= 0.75:
                    return True, f"High lexical overlap (Jaccard {jaccard:.2f})"

        return False, "Distinct or independent coverage"

    @staticmethod
    def calculate_independent_source_count(sources_domains: List[str], independence_groups: List[Optional[str]]) -> int:
        """Count unique independent source groups, treating syndicated copies as a single voice."""
        seen_domains: Set[str] = set()
        seen_groups: Set[str] = set()
        independent_count = 0

        for domain, group in zip(sources_domains, independence_groups):
            clean_dom = domain.lower().strip() if domain else "unknown"
            if group:
                clean_group = group.lower().strip()
                if clean_group not in seen_groups:
                    seen_groups.add(clean_group)
                    independent_count += 1
            else:
                if clean_dom not in seen_domains:
                    seen_domains.add(clean_dom)
                    independent_count += 1

        return max(1, independent_count)
