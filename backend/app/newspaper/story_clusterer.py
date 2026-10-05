"""story_clusterer.py — Duplicate Story & Coverage Clustering."""
import re
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.personalization.schemas import ScoredArticle
from app.personalization.scoring.semantic_scorer import SemanticScorer
from app.newspaper.editorial_scorer import EditorialScorer
from app.newspaper.models import StoryCluster, StoryClusterArticle


class StoryClusterer:
    """Detects multi-source coverage of the same event, groups them into clusters, and elects one primary article per cluster."""

    def __init__(
        self,
        session: Optional[AsyncSession] = None,
        similarity_threshold: float = settings.NEWSPAPER_CLUSTER_SIMILARITY_THRESHOLD,
    ):
        self.session = session
        self.similarity_threshold = similarity_threshold

    @staticmethod
    def _get_title_tokens(title: str) -> Set[str]:
        words = re.findall(r"\b[a-zA-Z0-9]{3,}\b", (title or "").lower())
        stopwords = {"the", "and", "for", "with", "from", "that", "this", "after", "into", "over", "about", "new"}
        return set(w for w in words if w not in stopwords)

    def are_stories_similar(
        self,
        art_a: Any,
        art_b: Any,
    ) -> Tuple[bool, float]:
        """Check if two articles cover the same event via title token overlap or embedding similarity."""
        title_a = getattr(art_a, "title", "") or ""
        title_b = getattr(art_b, "title", "") or ""

        tokens_a = self._get_title_tokens(title_a)
        tokens_b = self._get_title_tokens(title_b)

        # 1. Jaccard token overlap
        if tokens_a and tokens_b:
            intersection = len(tokens_a & tokens_b)
            union = len(tokens_a | tokens_b)
            jaccard = intersection / union if union > 0 else 0.0
            if jaccard >= 0.50:
                return True, round(jaccard, 4)

        # 2. Embedding Cosine Similarity
        emb_a = getattr(getattr(art_a, "analysis", None), "embedding", None) or getattr(art_a, "embedding", None)
        emb_b = getattr(getattr(art_b, "analysis", None), "embedding", None) or getattr(art_b, "embedding", None)

        if emb_a and emb_b:
            cos_sim = SemanticScorer.cosine_similarity(emb_a, emb_b)
            if cos_sim >= self.similarity_threshold:
                return True, round(cos_sim, 4)

        return False, 0.0

    async def cluster_and_elect_primary(
        self,
        candidates: List[ScoredArticle],
    ) -> Tuple[List[ScoredArticle], Dict[uuid.UUID, uuid.UUID]]:
        """
        Clusters similar candidate stories together and elects a single primary ScoredArticle per cluster.
        Returns:
            (list_of_primary_scored_articles, dict_mapping_article_id_to_cluster_id)
        """
        if not candidates:
            return [], {}

        clusters: List[List[Tuple[ScoredArticle, float]]] = []

        for cand in candidates:
            art = cand.article
            placed = False

            for cluster in clusters:
                rep_cand, _ = cluster[0]
                similar, sim_score = self.are_stories_similar(art, rep_cand.article)
                if similar:
                    cluster.append((cand, sim_score))
                    placed = True
                    break

            if not placed:
                clusters.append([(cand, 1.0)])

        primary_candidates: List[ScoredArticle] = []
        cluster_map: Dict[uuid.UUID, uuid.UUID] = {}

        for cluster in clusters:
            # Rank candidates within cluster by quality & relevance
            ranked_cluster = sorted(
                cluster,
                key=lambda item: (
                    item[0].relevance_score * EditorialScorer.compute_quality_score(item[0].article),
                    len(getattr(item[0].article, "content", "") or ""),
                ),
                reverse=True,
            )

            primary_cand, _ = ranked_cluster[0]
            primary_candidates.append(primary_cand)

            cluster_id = uuid.uuid4()
            cluster_key = f"cluster-{primary_cand.article.id.hex[:12]}"

            cluster_map[primary_cand.article.id] = cluster_id

            if self.session:
                stmt_c = select(StoryCluster).where(StoryCluster.cluster_key == cluster_key)
                res_c = await self.session.execute(stmt_c)
                existing_cluster = res_c.scalar_one_or_none()

                if not existing_cluster:
                    cluster_model = StoryCluster(
                        id=cluster_id,
                        cluster_key=cluster_key,
                    )
                    self.session.add(cluster_model)
                    await self.session.flush()
                else:
                    cluster_id = existing_cluster.id
                    cluster_map[primary_cand.article.id] = cluster_id

                for item_cand, sim_score in ranked_cluster:
                    cluster_map[item_cand.article.id] = cluster_id
                    stmt_sca = select(StoryClusterArticle).where(
                        StoryClusterArticle.cluster_id == cluster_id,
                        StoryClusterArticle.article_id == item_cand.article.id,
                    )
                    res_sca = await self.session.execute(stmt_sca)
                    existing_sca = res_sca.scalar_one_or_none()

                    if not existing_sca:
                        is_prim = (item_cand.article.id == primary_cand.article.id)
                        sca = StoryClusterArticle(
                            cluster_id=cluster_id,
                            article_id=item_cand.article.id,
                            similarity_score=sim_score,
                            is_primary=is_prim,
                        )
                        self.session.add(sca)
                await self.session.flush()

        return primary_candidates, cluster_map
