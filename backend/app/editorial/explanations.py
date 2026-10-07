"""explanations.py — Phase 17 Editorial Explanations & Daily Edition Summaries."""
from typing import List, Optional
from app.editorial.schemas import EditorialCandidate, EditorialRole, SectionType


class EditorialExplainer:
    """Generates concise, human-friendly editorial reasons and masthead summaries."""

    @staticmethod
    def generate_story_reason(
        candidate: EditorialCandidate,
        is_lead: bool = False,
        user_top_topics: Optional[List[str]] = None,
    ) -> str:
        """
        Produces a crisp, user-facing explanation for why this story appears in the edition.
        No raw math or model internals are exposed.
        """
        top_topics = user_top_topics or []
        first_topic = candidate.topics[0] if candidate.topics else (candidate.primary_category or "News").title()
        
        # 1. Lead Story Explanations
        if is_lead or candidate.editorial_role == EditorialRole.LEAD.value:
            if candidate.has_meaningful_update:
                return "Major story with new updates this morning."
            if any(t.lower() in [u.lower() for u in top_topics] for t in candidate.topics):
                return f"New development in {first_topic}, one of your strongest interests."
            if candidate.importance_score >= 0.85 and candidate.personal_relevance_score < 0.60:
                return "Major story with broad significance."
            return "Your top story today."

        # 2. Follow-Up Stories
        if candidate.editorial_role == EditorialRole.FOLLOW_UP.value or (candidate.is_read and candidate.has_meaningful_update):
            return f"Follow-up: New updates since you last read this story."

        # 3. Discovery Stories
        if candidate.editorial_role == EditorialRole.DISCOVERY.value or candidate.is_discovery_candidate:
            return f"Exploration into emerging developments in {first_topic}."

        # 4. For You Stories (High Personal Relevance)
        if candidate.assigned_section == SectionType.FOR_YOU.value or candidate.personal_relevance_score >= 0.80:
            if top_topics:
                matching = [t for t in candidate.topics if any(u.lower() in t.lower() or t.lower() in u.lower() for u in top_topics)]
                if matching:
                    return f"Because you frequently read about {matching[0]}."
            return f"High personal relevance to your reading interests."

        # 5. Trending / Developing Stories
        if candidate.is_developing or candidate.source_count >= 3:
            return f"Developing story covered by {candidate.source_count} independent sources."

        # 6. Section Specific Explanations
        cat_title = (candidate.primary_category or "General").title()
        return f"Important development in {cat_title}."

    @staticmethod
    def generate_editorial_summary(
        lead: Optional[EditorialCandidate],
        sections_map: dict,
        total_stories: int,
    ) -> str:
        """
        Generates a concise 1-2 sentence editorial masthead summary describing today's newspaper edition.
        """
        if not lead and not sections_map:
            return "Your personalized edition is ready with today's essential news."

        # Find dominant categories
        cat_counts = {}
        for sec_name, stories in sections_map.items():
            if sec_name in (SectionType.LEAD.value, SectionType.FOR_YOU.value, SectionType.DISCOVER.value):
                continue
            cat_counts[sec_name] = len(stories)

        sorted_cats = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)
        top_sections = [c[0].title().replace("_", " ") for c in sorted_cats[:2] if c[1] > 0]

        summary_parts = []
        if top_sections:
            sec_str = " and ".join(top_sections)
            summary_parts.append(f"{sec_str} feature prominently in your personalized edition")

        if lead:
            if lead.importance_score >= 0.85:
                summary_parts.append("while a major development leads the broader news")
            else:
                summary_parts.append("with your top chosen story heading today's coverage")

        if summary_parts:
            sentence = "Today, " + ", ".join(summary_parts) + "."
            return sentence

        return f"Today's curated edition features {total_stories} stories tailored to your interests."
