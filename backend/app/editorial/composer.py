"""composer.py — Phase 17 Editorial Composition Engine."""
import logging
from typing import Any, Dict, List, Optional, Tuple
from app.editorial.schemas import (
    EditorialCandidate,
    EditorialDecision,
    EditorialWeights,
    SectionType,
)
from app.editorial.diversity import EditorialDiversityFilter
from app.editorial.lead_selector import LeadStorySelector
from app.editorial.section_builder import EditorialSectionBuilder
from app.editorial.explanations import EditorialExplainer

logger = logging.getLogger(__name__)


class EditorialComposer:
    """
    Orchestrates the entire editorial composition process:
    Scoring -> Diversity Filtering -> Lead Selection -> Section Mapping -> Explanation Generation.
    """

    def __init__(self, weights: Optional[EditorialWeights] = None):
        self.weights = weights or EditorialWeights()
        self.diversity_filter = EditorialDiversityFilter(self.weights)
        self.lead_selector = LeadStorySelector()
        self.section_builder = EditorialSectionBuilder(self.weights)
        self.explainer = EditorialExplainer()

    def compose_edition(
        self,
        candidates: List[EditorialCandidate],
        user_top_topics: Optional[List[str]] = None,
        target_story_count: int = 25,
    ) -> Tuple[
        Optional[EditorialCandidate],
        Dict[str, List[EditorialCandidate]],
        List[Tuple[str, str, int]],
        str,
        List[EditorialDecision],
    ]:
        """
        Executes the editorial pipeline on raw candidates.
        
        Returns:
            (lead_story, sections_map, section_metadata, editorial_summary, debug_decisions)
        """
        if not candidates:
            summary = "No stories available for today's edition."
            return None, {}, [], summary, []

        w = self.weights
        scored_candidates: List[EditorialCandidate] = []

        # 1. Centralized Editorial Scoring
        for cand in candidates:
            # Read penalty: if completed reading and NO updates, apply penalty; if updates exist, no penalty
            read_penalty = 0.0
            if cand.is_read and not cand.has_meaningful_update:
                read_penalty = w.read_penalty_factor * max(0.5, cand.user_read_percentage)

            raw_score = (
                w.weight_personal_relevance * cand.personal_relevance_score
                + w.weight_global_importance * cand.importance_score
                + w.weight_recency * cand.recency_score
                + w.weight_story_activity * cand.activity_score
                + w.weight_source_quality * cand.quality_score
                + w.weight_novelty * cand.novelty_score
                + w.weight_user_affinity * cand.user_affinity_score
                + cand.public_importance_bonus
                - read_penalty
                - cand.duplicate_coverage_penalty
            )

            cand.editorial_score = max(0.05, min(0.99, raw_score))
            scored_candidates.append(cand)

        # Sort by editorial score descending
        scored_candidates.sort(key=lambda c: c.editorial_score, reverse=True)

        # 2. Multi-Dimensional Diversity & Anti-Monopoly Filtering
        diversified_candidates, diversity_audit = self.diversity_filter.apply_diversity(
            scored_candidates, target_count=target_story_count
        )

        # 3. Lead Story Selection
        lead_story, remaining_candidates = self.lead_selector.select_lead(diversified_candidates)

        # 4. Section Mapping & Role Distribution
        sections_map, section_metadata = self.section_builder.build_sections(
            lead_story=lead_story,
            candidates=remaining_candidates,
        )

        # 5. Editorial Explanations Generation
        if lead_story:
            lead_story.reason = self.explainer.generate_story_reason(
                lead_story, is_lead=True, user_top_topics=user_top_topics
            )

        for sec_name, stories in sections_map.items():
            for story in stories:
                if not story.reason:
                    story.reason = self.explainer.generate_story_reason(
                        story, is_lead=False, user_top_topics=user_top_topics
                    )

        total_selected = (1 if lead_story else 0) + sum(
            len(st_list) for k, st_list in sections_map.items() if k != SectionType.LEAD.value
        )

        # 6. Masthead Editorial Summary
        editorial_summary = self.explainer.generate_editorial_summary(
            lead=lead_story,
            sections_map=sections_map,
            total_stories=total_selected,
        )

        # 7. Audit Decisions for Admin Debug
        selected_ids = set()
        if lead_story:
            selected_ids.add(str(lead_story.article_id))
        for stories in sections_map.values():
            for s in stories:
                selected_ids.add(str(s.article_id))

        debug_decisions: List[EditorialDecision] = []
        for cand in scored_candidates:
            cand_id_str = str(cand.article_id)
            is_sel = cand_id_str in selected_ids
            decision = EditorialDecision(
                item_id=cand_id_str,
                title=cand.title,
                editorial_score=round(cand.editorial_score, 4),
                role=cand.editorial_role,
                section=cand.assigned_section,
                decision="SELECTED" if is_sel else "EXCLUDED",
                reason=cand.reason or ("Excluded by diversity or score cutoff" if not is_sel else "Selected"),
                factors={
                    "personal_relevance": round(cand.personal_relevance_score, 3),
                    "global_importance": round(cand.importance_score, 3),
                    "recency": round(cand.recency_score, 3),
                    "story_activity": round(cand.activity_score, 3),
                    "source_quality": round(cand.quality_score, 3),
                    "is_read": 1.0 if cand.is_read else 0.0,
                    "has_updates": 1.0 if cand.has_meaningful_update else 0.0,
                },
            )
            debug_decisions.append(decision)

        return lead_story, sections_map, section_metadata, editorial_summary, debug_decisions
