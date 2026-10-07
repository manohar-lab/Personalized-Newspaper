"""lead_selector.py — Phase 17 Lead Story Selection Engine."""
from typing import List, Optional, Tuple
from app.editorial.schemas import EditorialCandidate, EditorialRole


class LeadStorySelector:
    """
    Selects the single most compelling lead story for today's newspaper edition.
    Balances global public importance against personal relevance, freshness, and multi-source credibility.
    """

    def __init__(
        self,
        weight_importance: float = 0.35,
        weight_personal_relevance: float = 0.30,
        weight_recency: float = 0.15,
        weight_story_activity: float = 0.10,
        weight_quality: float = 0.10,
    ):
        self.weight_importance = weight_importance
        self.weight_personal_relevance = weight_personal_relevance
        self.weight_recency = weight_recency
        self.weight_story_activity = weight_story_activity
        self.weight_quality = weight_quality

    def select_lead(
        self,
        candidates: List[EditorialCandidate],
    ) -> Tuple[Optional[EditorialCandidate], List[EditorialCandidate]]:
        """
        Elects the edition's lead story from candidates.
        
        Returns:
            (lead_candidate, remaining_candidates)
        """
        if not candidates:
            return None, []

        best_candidate: Optional[EditorialCandidate] = None
        best_lead_score = -1.0
        best_index = -1

        for idx, cand in enumerate(candidates):
            # Lead Eligibility: Exclude pure discovery or low-information briefs if better candidates exist
            if cand.is_read and not cand.has_meaningful_update:
                # Fully read without updates is deprioritized for lead
                read_penalty = 0.40
            else:
                read_penalty = 0.0

            # Visual bonus: stories with high quality images make better leads
            image_bonus = 0.05 if cand.top_image_url else 0.0

            # Multi-source credibility bonus
            multi_source_bonus = min(0.10, 0.02 * cand.source_count)

            # Breaking / developing event urgency
            urgency_bonus = 0.10 if (cand.is_breaking or cand.is_developing) else 0.0

            lead_score = (
                self.weight_importance * cand.importance_score
                + self.weight_personal_relevance * cand.personal_relevance_score
                + self.weight_recency * cand.recency_score
                + self.weight_story_activity * cand.activity_score
                + self.weight_quality * cand.quality_score
                + image_bonus
                + multi_source_bonus
                + urgency_bonus
                + cand.public_importance_bonus
                - read_penalty
            )

            # Major overriding global event rule: if global importance is extremely high (e.g. >= 0.92),
            # give it strong priority even if personal relevance is modest.
            if cand.importance_score >= 0.92:
                lead_score += 0.15

            if lead_score > best_lead_score:
                best_lead_score = lead_score
                best_candidate = cand
                best_index = idx

        if best_candidate is not None:
            best_candidate.editorial_role = EditorialRole.LEAD.value
            remaining = [c for i, c in enumerate(candidates) if i != best_index]
            return best_candidate, remaining

        return None, candidates
