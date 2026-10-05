from typing import List, Optional, Tuple
from app.newspaper.editorial_scorer import ScoredCandidateStory


class LeadStorySelector:
    """
    Selects the single primary lead story for a user's edition.
    
    The lead is chosen using a composite lead score that emphasizes:
    - High personal relevance (most important for THIS user)
    - Strong editorial score & importance
    - High content quality (full readable text, length, clean metadata)
    """

    def select_lead(
        self, candidates: List[ScoredCandidateStory]
    ) -> Tuple[Optional[ScoredCandidateStory], List[ScoredCandidateStory]]:
        """
        Returns (lead_story, remaining_candidates).
        """
        if not candidates:
            return None, []

        def calculate_lead_suitability(cand: ScoredCandidateStory) -> float:
            article = cand.scored_article.article
            # Personal relevance is paramount
            rel = cand.scored_article.relevance_score
            editorial = cand.editorial_score
            quality = cand.quality_score

            # Content length bonus (prefer stories with substantial content for lead placement)
            content_len = len(article.content or "")
            len_bonus = 0.10 if content_len > 800 else (0.05 if content_len > 300 else 0.0)
            
            # Full text bonus
            full_text_bonus = 0.10 if article.is_full_text_available else 0.0

            # Image bonus (lead story looks great with an image)
            image_bonus = (
                0.05
                if (getattr(article, "image_url", None) or getattr(article, "top_image_url", None))
                else 0.0
            )

            suitability = (
                0.45 * rel
                + 0.25 * editorial
                + 0.15 * quality
                + len_bonus
                + full_text_bonus
                + image_bonus
            )
            return suitability

        ranked_for_lead = sorted(
            candidates, key=calculate_lead_suitability, reverse=True
        )

        lead = ranked_for_lead[0]
        remaining = [c for c in candidates if c.scored_article.article.id != lead.scored_article.article.id]

        return lead, remaining
