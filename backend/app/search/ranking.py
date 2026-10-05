"""ranking.py — Phase 11 Hybrid Search Ranking and Scoring."""
import uuid
from typing import Dict, List, Optional
from app.core.config import settings
from app.models.article import Article
from app.search.schemas import ParsedQueryInfo, SearchResultItem


class HybridSearchRanker:
    """
    Ranks search results using a hybrid formula:
    - Full-text keyword match score (50%)
    - Semantic vector similarity score (50%)
    - Topic matching boost (+15%)
    - Entity matching boost (+15%)
    - Keyword matching boost (+10%)
    - Personal relevance integration (15% weighting on final score)
    """

    def __init__(
        self,
        full_text_weight: Optional[float] = None,
        semantic_weight: Optional[float] = None,
        personalization_weight: Optional[float] = None,
        topic_boost: Optional[float] = None,
        entity_boost: Optional[float] = None,
        keyword_boost: Optional[float] = None,
    ):
        self.full_text_weight = full_text_weight or settings.SEARCH_FULL_TEXT_WEIGHT
        self.semantic_weight = semantic_weight or settings.SEARCH_SEMANTIC_WEIGHT
        self.personalization_weight = personalization_weight or settings.SEARCH_PERSONALIZATION_WEIGHT
        self.topic_boost = topic_boost or settings.SEARCH_TOPIC_BOOST
        self.entity_boost = entity_boost or settings.SEARCH_ENTITY_BOOST
        self.keyword_boost = keyword_boost or settings.SEARCH_KEYWORD_BOOST

    def rank_results(
        self,
        articles: List[Article],
        full_text_scores: Dict[uuid.UUID, float],
        semantic_scores: Dict[uuid.UUID, float],
        personal_relevance_scores: Dict[uuid.UUID, float],
        parsed_query: ParsedQueryInfo,
        has_user_profile: bool = False,
    ) -> List[SearchResultItem]:
        """
        Calculates hybrid scores and returns ranked SearchResultItem list sorted by final_score descending.
        """
        results: List[SearchResultItem] = []

        detected_topics_lower = {t.lower() for t in parsed_query.detected_topics}
        detected_entities_lower = {e.lower() for e in parsed_query.detected_entities}

        for art in articles:
            ft_score = full_text_scores.get(art.id, 0.0)
            sem_score = semantic_scores.get(art.id, 0.0)

            # Base Search Score
            if sem_score > 0.0:
                base_score = (ft_score * self.full_text_weight) + (sem_score * self.semantic_weight)
            else:
                # Fallback purely to full text if semantic unavailable
                base_score = ft_score

            # Topic Boost
            art_topics = [t.name if hasattr(t, "name") else str(t) for t in (art.topics or [])]
            art_topics_lower = {t.lower() for t in art_topics}
            if art.primary_category:
                art_topics_lower.add(art.primary_category.lower())

            topic_boost_val = 0.0
            matched_topic_name = None
            for dt in detected_topics_lower:
                if any(dt in at for at in art_topics_lower):
                    topic_boost_val = self.topic_boost
                    matched_topic_name = dt.title()
                    break

            # Entity Boost
            art_entities = [e.name if hasattr(e, "name") else str(e) for e in (art.entities or [])]
            art_entities_lower = {e.lower() for e in art_entities}

            entity_boost_val = 0.0
            matched_entity_name = None
            for de in detected_entities_lower:
                if any(de in ae for ae in art_entities_lower):
                    entity_boost_val = self.entity_boost
                    matched_entity_name = de.title()
                    break

            # Keyword Boost
            art_keywords = [k.keyword.lower() if hasattr(k, "keyword") else str(k).lower() for k in (getattr(art, "keywords", []) or [])]
            kw_boost_val = 0.0
            for clean_kw in parsed_query.clean_keywords.lower().split():
                if any(clean_kw in ak for ak in art_keywords):
                    kw_boost_val = self.keyword_boost
                    break

            # Total Search Score
            search_score = min(1.0, base_score + topic_boost_val + entity_boost_val + kw_boost_val)

            # Personal Relevance Integration
            personal_rel = personal_relevance_scores.get(art.id)
            if has_user_profile and personal_rel is not None:
                # 85% search score, 15% personal relevance
                final_score = (
                    ((1.0 - self.personalization_weight) * search_score)
                    + (self.personalization_weight * personal_rel)
                )
            else:
                final_score = search_score

            # Match Explanation
            explanation = None
            if matched_topic_name:
                explanation = f"Matches: {matched_topic_name}"
            elif matched_entity_name:
                explanation = f"Matches: {matched_entity_name}"
            elif has_user_profile and personal_rel and personal_rel > 0.70 and art_topics:
                explanation = f"Matches your interest in {art_topics[0]}"

            item = SearchResultItem(
                article_id=art.id,
                title=art.title,
                summary=art.analysis.summary if art.analysis and art.analysis.summary else art.description,
                source_name=art.source.name if art.source else (art.source_name or "Independent Source"),
                published_at=art.published_at,
                primary_category=art.primary_category,
                topics=art_topics,
                entities=art_entities,
                top_image_url=art.image_url,
                reading_time_minutes=art.reading_time_minutes or 3,
                is_full_text_available=art.is_full_text_available,
                full_text_score=round(ft_score, 4),
                semantic_score=round(sem_score, 4),
                search_score=round(search_score, 4),
                personal_relevance_score=round(personal_rel, 4) if personal_rel is not None else None,
                final_score=round(final_score, 4),
                match_explanation=explanation,
            )
            results.append(item)

        # Sort by final score descending, breaking ties with publication recency
        results.sort(
            key=lambda r: (r.final_score, r.published_at.timestamp() if r.published_at else 0),
            reverse=True,
        )
        return results
