"""story_lifecycle.py — Story Importance, Quality, Status, Independent Sources, and Primary/Latest Article Selection."""
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Set, Tuple

from app.source_intelligence.quality_metrics import QualityMetricsCalculator


class StoryLifecycleManager:
    """Manages dynamic story lifecycle, independent source accounting, importance, quality, and status transitions."""

    @staticmethod
    def _get_text_tokens(text: str) -> Set[str]:
        if not text:
            return set()
        words = re.findall(r"\b[a-zA-Z0-9]{3,}\b", text.lower())
        stopwords = {"the", "and", "for", "with", "from", "that", "this", "after", "into", "over", "about", "new"}
        return set(w for w in words if w not in stopwords)

    @classmethod
    def are_articles_syndicated(cls, art_a: Any, art_b: Any) -> bool:
        """Determines if two articles are syndicated copies based on high content/summary token overlap."""
        text_a = getattr(art_a, "content", "") or getattr(art_a, "summary", "") or getattr(art_a, "title", "") or ""
        text_b = getattr(art_b, "content", "") or getattr(art_b, "summary", "") or getattr(art_b, "title", "") or ""

        tokens_a = cls._get_text_tokens(text_a)
        tokens_b = cls._get_text_tokens(text_b)
        if not tokens_a or not tokens_b:
            return False

        inter = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)
        jaccard = inter / union if union > 0 else 0.0
        return jaccard >= 0.75

    @classmethod
    def compute_independent_source_count(cls, articles: List[Any]) -> Tuple[int, int, List[str]]:
        """
        Calculates (total_source_count, independent_source_count, list_of_unique_sources).
        Syndicated identical copies do not increment independent source count.
        """
        if not articles:
            return 0, 0, []

        source_names: Set[str] = set()
        for art in articles:
            src = getattr(art, "source_name", None)
            if not src and getattr(art, "source", None):
                src = getattr(art.source, "name", None)
            if src:
                source_names.add(src.strip())
            else:
                source_names.add("Independent")

        # Cluster articles by syndication text overlap
        independent_clusters: List[List[Any]] = []
        for art in articles:
            placed = False
            for cluster in independent_clusters:
                if cls.are_articles_syndicated(art, cluster[0]):
                    cluster.append(art)
                    placed = True
                    break
            if not placed:
                independent_clusters.append([art])

        independent_count = len(independent_clusters)
        total_source_count = len(source_names)
        # Independent count cannot exceed total sources, but at least 1
        independent_count = max(1, min(total_source_count, independent_count))

        return total_source_count, independent_count, sorted(list(source_names))

    @staticmethod
    def compute_story_importance(
        articles: List[Any],
        independent_source_count: int,
        latest_update: Optional[datetime] = None,
    ) -> float:
        """
        Calculates composite story importance (0.0 - 1.0).
        High source diversity and original reporting boost importance.
        """
        if not articles:
            return 0.5

        # 1. Highest article importance among members
        max_art_imp = 0.5
        for art in articles:
            analysis = getattr(art, "analysis", None)
            imp = getattr(analysis, "importance_score", None) if analysis else getattr(art, "importance_score", 0.5)
            if imp is not None and imp > max_art_imp:
                max_art_imp = float(imp)

        # 2. Independent source factor (diminishing returns)
        # 1 source -> 0.22, 2 sources -> 0.39, 4 sources -> 0.63, 8+ sources -> 0.86+
        source_factor = 1.0 - math.exp(-float(independent_source_count) / 4.0)

        # 3. Recency factor
        recency_factor = 0.5
        if latest_update:
            now = datetime.now(timezone.utc)
            if latest_update.tzinfo is None:
                latest_update = latest_update.replace(tzinfo=timezone.utc)
            age_hours = max(0.0, (now - latest_update).total_seconds() / 3600.0)
            recency_factor = math.exp(-age_hours / 48.0)

        importance = (
            0.40 * max_art_imp
            + 0.35 * source_factor
            + 0.25 * recency_factor
        )
        return round(max(0.0, min(1.0, importance)), 4)

    @staticmethod
    def compute_story_quality(
        articles: List[Any],
        independent_source_count: int,
        has_summary: bool = True,
    ) -> float:
        """Calculates story quality score from member article qualities and coverage diversity."""
        if not articles:
            return 0.5

        qualities = []
        for art in articles:
            analysis = getattr(art, "analysis", None)
            q = getattr(analysis, "article_quality_score", None) if analysis else None
            if q is None:
                q = getattr(art, "quality_score", 0.5)
            qualities.append(float(q or 0.5))

        avg_quality = sum(qualities) / len(qualities)
        diversity_bonus = min(0.15, (independent_source_count - 1) * 0.05)
        summary_bonus = 0.05 if has_summary else 0.0

        quality = avg_quality + diversity_bonus + summary_bonus
        return round(max(0.0, min(1.0, quality)), 4)

    @staticmethod
    def compute_activity_and_status(
        articles: List[Any],
        last_updated_at: Optional[datetime] = None,
    ) -> Tuple[float, str]:
        """
        Calculates activity score (0.0 - 1.0) and status:
        ACTIVE | DEVELOPING | STABLE | RESOLVED | ARCHIVED
        """
        now = datetime.now(timezone.utc)
        if not articles:
            return 0.5, "ACTIVE"

        # Count articles published in last 6 hours
        recent_6h_count = 0
        recent_24h_count = 0

        for art in articles:
            pub = getattr(art, "published_at", None) or getattr(art, "created_at", None)
            if pub:
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
                age_hours = max(0.0, (now - pub).total_seconds() / 3600.0)
                if age_hours <= 6.0:
                    recent_6h_count += 1
                if age_hours <= 24.0:
                    recent_24h_count += 1

        # Activity score based on arrival rate and volume
        activity_score = min(1.0, (recent_6h_count * 0.3) + (recent_24h_count * 0.1) + 0.2)

        # Status determination
        if recent_6h_count >= 2:
            status = "DEVELOPING"
        elif recent_24h_count >= 1:
            status = "ACTIVE"
        else:
            if last_updated_at:
                if last_updated_at.tzinfo is None:
                    last_updated_at = last_updated_at.replace(tzinfo=timezone.utc)
                age_days = (now - last_updated_at).total_seconds() / 86400.0
                if age_days > 7.0:
                    status = "ARCHIVED"
                elif age_days > 2.0:
                    status = "STABLE"
                else:
                    status = "ACTIVE"
            else:
                status = "ACTIVE"

        return round(activity_score, 4), status

    @classmethod
    def select_primary_article(cls, articles: List[Any]) -> Optional[Any]:
        """
        Eelects the primary foundational article:
        Prefers high quality, full-text availability, and earliest credible reporting.
        """
        if not articles:
            return None
        if len(articles) == 1:
            return articles[0]

        def ranking_key(art):
            analysis = getattr(art, "analysis", None)
            quality = float(getattr(analysis, "article_quality_score", 0.5) or 0.5) if analysis else 0.5
            content_len = len(getattr(art, "content", "") or "")
            pub = getattr(art, "published_at", None) or getattr(art, "created_at", None)
            pub_ts = pub.timestamp() if pub else 0
            # Higher quality and content length, earlier publication timestamp
            return (quality * 10.0 + min(5.0, content_len / 500.0), -pub_ts)

        sorted_articles = sorted(articles, key=ranking_key, reverse=True)
        return sorted_articles[0]

    @classmethod
    def select_latest_article(cls, articles: List[Any]) -> Optional[Any]:
        """Eelects the newest meaningful article for the story."""
        if not articles:
            return None
        if len(articles) == 1:
            return articles[0]

        def pub_time(art):
            pub = getattr(art, "published_at", None) or getattr(art, "created_at", None)
            return pub.timestamp() if pub else 0

        sorted_articles = sorted(articles, key=pub_time, reverse=True)
        return sorted_articles[0]
