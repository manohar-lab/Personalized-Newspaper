"""ranking.py — Phase 24 Hybrid Search Ranking and Scoring."""
import re
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
    - Exact headline match boost (+25%)
    - Topic matching boost (+15%)
    - Entity matching boost (+15%)
    - Keyword matching boost (+10%)
    - Personal relevance integration (15% weighting on final score, bounded to preserve search relevance)
    - Source quality weighting
    - Sorting by relevance, newest, or importance
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
        sort_by: str = "relevance",
        muted_topics: Optional[set] = None,
        muted_sources: Optional[set] = None,
    ) -> List[SearchResultItem]:
        """
        Calculates hybrid scores and returns ranked SearchResultItem list.
        """
        results: List[SearchResultItem] = []
        muted_topics = muted_topics or set()
        muted_sources = muted_sources or set()

        clean_kw_lower = (parsed_query.clean_keywords or parsed_query.raw_query or "").strip().lower()
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

            # Exact Headline Match Boost
            art_title_lower = (art.title or "").strip().lower()
            exact_headline_boost = 0.0
            if clean_kw_lower and (clean_kw_lower == art_title_lower or clean_kw_lower in art_title_lower):
                # Strong boost for headline matches
                if clean_kw_lower == art_title_lower:
                    exact_headline_boost = 0.30
                else:
                    exact_headline_boost = 0.15

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
            art_keywords = [
                k.keyword.lower() if hasattr(k, "keyword") else str(k).lower()
                for k in (getattr(art, "keywords", []) or [])
            ]
            kw_boost_val = 0.0
            for kw_token in clean_kw_lower.split():
                if len(kw_token) > 2 and any(kw_token in ak for ak in art_keywords):
                    kw_boost_val = self.keyword_boost
                    break

            # Total Search Score
            search_score = min(
                1.0,
                base_score + exact_headline_boost + topic_boost_val + entity_boost_val + kw_boost_val,
            )

            # Check for muted topics or sources
            is_muted = False
            src_name = art.source.name if art.source else (art.source_name or "")
            if src_name.lower() in muted_sources:
                is_muted = True
            for at_low in art_topics_lower:
                if at_low in muted_topics:
                    is_muted = True
                    break

            # Personal Relevance Integration
            personal_rel = personal_relevance_scores.get(art.id)
            if has_user_profile and personal_rel is not None:
                # Primary search score anchor (85%), personal relevance (15%)
                final_score = (
                    ((1.0 - self.personalization_weight) * search_score)
                    + (self.personalization_weight * personal_rel)
                )
            else:
                final_score = search_score

            # Demote muted items unless query specifically asked for them
            if is_muted:
                final_score = max(0.01, final_score * 0.3)

            # Match Explanation
            explanation = None
            if exact_headline_boost > 0:
                explanation = "Headline match"
            elif matched_topic_name:
                explanation = f"Matches: {matched_topic_name}"
            elif matched_entity_name:
                explanation = f"Matches: {matched_entity_name}"
            elif has_user_profile and personal_rel and personal_rel > 0.70 and art_topics:
                explanation = f"Matches your interest in {art_topics[0]}"

            # Extraction status & paywall info
            is_paywalled = (getattr(art, "extraction_status", "") == "PAYWALL")
            source_url = getattr(art, "source_url", getattr(art, "canonical_url", None))
            author = getattr(art, "author", None)

            # Summary handling (fallback gracefully if missing)
            summary = None
            if hasattr(art, "analysis") and art.analysis and art.analysis.summary:
                summary = art.analysis.summary
            elif art.description:
                summary = art.description
            elif art.content:
                summary = art.content[:240] + "..." if len(art.content) > 240 else art.content

            item = SearchResultItem(
                article_id=art.id,
                title=art.title,
                summary=summary,
                source_name=src_name or "Independent Source",
                source_url=source_url,
                author=author,
                published_at=art.published_at,
                primary_category=art.primary_category,
                topics=art_topics,
                entities=art_entities,
                top_image_url=art.image_url,
                reading_time_minutes=art.reading_time_minutes or 3,
                is_full_text_available=art.is_full_text_available,
                is_paywalled=is_paywalled,
                full_text_score=round(ft_score, 4),
                semantic_score=round(sem_score, 4),
                search_score=round(search_score, 4),
                personal_relevance_score=round(personal_rel, 4) if personal_rel is not None else None,
                final_score=round(final_score, 4),
                match_explanation=explanation,
            )
            results.append(item)

        # Sorting
        sort_mode = (sort_by or "relevance").lower().strip()
        if sort_mode == "newest":
            results.sort(
                key=lambda r: (r.published_at.timestamp() if r.published_at else 0, r.final_score),
                reverse=True,
            )
        elif sort_mode == "importance":
            # Sort by search_score / final_score then recency
            results.sort(
                key=lambda r: (r.search_score, r.final_score, r.published_at.timestamp() if r.published_at else 0),
                reverse=True,
            )
        else:
            # Default: most relevant (final score desc, breaking ties with recency)
            results.sort(
                key=lambda r: (r.final_score, r.published_at.timestamp() if r.published_at else 0),
                reverse=True,
            )

        return results
