"""section_builder.py — Phase 17 Editorial Section Assignment & Role Distribution Engine."""
from typing import Dict, List, Optional, Tuple
from app.editorial.schemas import (
    EditorialCandidate,
    EditorialRole,
    EditorialWeights,
    SectionType,
)


class EditorialSectionBuilder:
    """Assigns stories to structured editorial sections, distributes roles, and enforces section balance."""

    def __init__(self, weights: Optional[EditorialWeights] = None):
        self.weights = weights or EditorialWeights()
        self.max_stories_per_section = self.weights.max_stories_per_section

    def map_category_to_section(self, candidate: EditorialCandidate) -> str:
        """Determines the appropriate topic section based on category, topics, and entities."""
        cat = (candidate.primary_category or "").upper()
        topics = [t.upper() for t in candidate.topics]
        entities = [e.upper() for e in candidate.entities]
        title_upper = candidate.title.upper()

        # 1. India specific detection
        if (
            "INDIA" in cat
            or any("INDIA" in t or "BHARAT" in t or "DELHI" in t or "MUMBAI" in t for t in topics)
            or any("INDIA" in e or "MODI" in e or "ISRO" in e for e in entities)
            or "INDIA" in title_upper
        ):
            return SectionType.INDIA.value

        # 2. Technology & AI
        if (
            cat in ("TECHNOLOGY", "TECH", "AI", "COMPUTING")
            or any(t in ("TECHNOLOGY", "AI", "ARTIFICIAL INTELLIGENCE", "MACHINE LEARNING", "SOFTWARE", "HARDWARE", "ROBOTICS", "CYBERSECURITY") for t in topics)
        ):
            return SectionType.TECHNOLOGY.value

        # 3. Business & Economy
        if (
            cat in ("BUSINESS", "FINANCE", "ECONOMY", "MARKETS")
            or any(t in ("BUSINESS", "FINANCE", "ECONOMY", "MARKETS", "STARTUPS", "VENTURE CAPITAL", "CRYPTO") for t in topics)
        ):
            return SectionType.BUSINESS.value

        # 4. Science & Nature
        if (
            cat in ("SCIENCE", "SPACE", "HEALTH", "ENVIRONMENT", "MEDICINE")
            or any(t in ("SCIENCE", "SPACE", "ASTRONOMY", "PHYSICS", "BIOLOGY", "CLIMATE", "HEALTH", "MEDICINE") for t in topics)
        ):
            return SectionType.SCIENCE.value

        # 5. World & International
        if (
            cat in ("WORLD", "INTERNATIONAL", "GLOBAL", "GEOPOLITICS")
            or any(t in ("WORLD", "INTERNATIONAL", "DIPLOMACY", "GLOBAL AFFAIRS") for t in topics)
        ):
            return SectionType.WORLD.value

        # 6. Sports
        if (
            cat in ("SPORTS", "ATHLETICS", "FOOTBALL", "CRICKET", "TENNIS")
            or any(t in ("SPORTS", "FOOTBALL", "CRICKET", "TENNIS", "BASKETBALL", "F1") for t in topics)
        ):
            return SectionType.SPORTS.value

        # 7. Entertainment & Culture
        if (
            cat in ("ENTERTAINMENT", "CULTURE", "GAMING", "MOVIES", "MUSIC")
            or any(t in ("ENTERTAINMENT", "MOVIES", "MUSIC", "GAMING", "ARTS", "CULTURE") for t in topics)
        ):
            return SectionType.ENTERTAINMENT.value

        return SectionType.TOP_STORIES.value

    def build_sections(
        self,
        lead_story: Optional[EditorialCandidate],
        candidates: List[EditorialCandidate],
    ) -> Tuple[Dict[str, List[EditorialCandidate]], List[Tuple[str, str, int]]]:
        """
        Organizes candidates into ordered editorial sections:
        - FOR_YOU: Exceptional personal relevance
        - TOP_STORIES: High-value general and breaking stories
        - Domain Sections (TECHNOLOGY, BUSINESS, SCIENCE, WORLD, INDIA, SPORTS, ENTERTAINMENT)
        - DISCOVER: Emerging topics / exploration
        
        Assigns editorial roles (TOP_STORY, STANDARD, BRIEF, DISCOVERY, TRENDING, FOLLOW_UP).
        
        Returns:
            (sections_map, section_metadata_list [(section_type, display_title, display_order)])
        """
        sections_map: Dict[str, List[EditorialCandidate]] = {}

        # 1. Lead Section (if lead exists)
        if lead_story:
            lead_story.assigned_section = SectionType.LEAD.value
            lead_story.editorial_role = EditorialRole.LEAD.value
            sections_map[SectionType.LEAD.value] = [lead_story]

        # 2. Extract For You and Discover candidates
        for_you_pool: List[EditorialCandidate] = []
        discover_pool: List[EditorialCandidate] = []
        regular_pool: List[EditorialCandidate] = []

        for cand in candidates:
            # Check follow-up role
            if cand.is_read and cand.has_meaningful_update:
                cand.editorial_role = EditorialRole.FOLLOW_UP.value
            elif cand.is_developing or cand.source_count >= 3:
                cand.editorial_role = EditorialRole.TRENDING.value

            # Check Discover eligibility (emerging interest or high novelty with modest relevance)
            if cand.is_discovery_candidate or (cand.novelty_score >= 0.75 and cand.personal_relevance_score < 0.65):
                cand.editorial_role = EditorialRole.DISCOVERY.value
                discover_pool.append(cand)
            # Check For You eligibility (exceptional personal relevance)
            elif cand.personal_relevance_score >= 0.85 and len(for_you_pool) < 4:
                for_you_pool.append(cand)
            else:
                regular_pool.append(cand)

        # 3. Add FOR_YOU section if populated
        if for_you_pool:
            for item in for_you_pool:
                item.assigned_section = SectionType.FOR_YOU.value
                if item.editorial_role == EditorialRole.STANDARD.value:
                    item.editorial_role = EditorialRole.TOP_STORY.value
            sections_map[SectionType.FOR_YOU.value] = for_you_pool

        # 4. Partition remaining regular candidates into Domain Sections & TOP_STORIES
        domain_sections: Dict[str, List[EditorialCandidate]] = {}
        for cand in regular_pool:
            target_sec = self.map_category_to_section(cand)
            if target_sec not in domain_sections:
                domain_sections[target_sec] = []

            # Enforce max stories per section
            if len(domain_sections[target_sec]) < self.max_stories_per_section:
                cand.assigned_section = target_sec
                domain_sections[target_sec].append(cand)
            else:
                # If section full, attempt TOP_STORIES or overflow
                if len(domain_sections.get(SectionType.TOP_STORIES.value, [])) < self.max_stories_per_section:
                    cand.assigned_section = SectionType.TOP_STORIES.value
                    domain_sections.setdefault(SectionType.TOP_STORIES.value, []).append(cand)

        # 5. Distribute editorial roles (TOP_STORY, STANDARD, BRIEF) within domain sections
        for sec_name, stories in domain_sections.items():
            if not stories:
                continue
            # Sort stories within section by editorial score
            sorted_stories = sorted(stories, key=lambda s: s.editorial_score, reverse=True)
            for idx, story in enumerate(sorted_stories):
                if story.editorial_role not in (EditorialRole.FOLLOW_UP.value, EditorialRole.TRENDING.value):
                    if idx == 0 and sec_name != SectionType.DISCOVER.value:
                        story.editorial_role = EditorialRole.TOP_STORY.value
                    elif idx >= 3 and story.editorial_score < 0.65:
                        story.editorial_role = EditorialRole.BRIEF.value
                    else:
                        story.editorial_role = EditorialRole.STANDARD.value
            sections_map[sec_name] = sorted_stories

        # 6. Add DISCOVER section (capped at 3 items so it doesn't dominate)
        if discover_pool:
            discover_items = discover_pool[:3]
            for d in discover_items:
                d.assigned_section = SectionType.DISCOVER.value
                d.editorial_role = EditorialRole.DISCOVERY.value
            sections_map[SectionType.DISCOVER.value] = discover_items

        # 7. Generate Section Ordering Metadata
        # Standard editorial ordering: LEAD -> TOP_STORIES -> FOR_YOU -> TECHNOLOGY -> BUSINESS -> SCIENCE -> WORLD -> INDIA -> SPORTS -> ENTERTAINMENT -> DISCOVER
        section_titles = {
            SectionType.LEAD.value: "Lead Story",
            SectionType.TOP_STORIES.value: "Top Stories",
            SectionType.FOR_YOU.value: "For You",
            SectionType.TECHNOLOGY.value: "Technology & AI",
            SectionType.BUSINESS.value: "Business & Economy",
            SectionType.SCIENCE.value: "Science & Discovery",
            SectionType.WORLD.value: "World News",
            SectionType.INDIA.value: "India National",
            SectionType.SPORTS.value: "Sports",
            SectionType.ENTERTAINMENT.value: "Culture & Entertainment",
            SectionType.DISCOVER.value: "Discover Something New",
        }

        canonical_order = [
            SectionType.LEAD.value,
            SectionType.TOP_STORIES.value,
            SectionType.FOR_YOU.value,
            SectionType.TECHNOLOGY.value,
            SectionType.BUSINESS.value,
            SectionType.SCIENCE.value,
            SectionType.WORLD.value,
            SectionType.INDIA.value,
            SectionType.SPORTS.value,
            SectionType.ENTERTAINMENT.value,
            SectionType.DISCOVER.value,
        ]

        section_metadata: List[Tuple[str, str, int]] = []
        display_order = 1
        for sec_type in canonical_order:
            if sec_type in sections_map and len(sections_map[sec_type]) > 0:
                title = section_titles.get(sec_type, sec_type.replace("_", " ").title())
                section_metadata.append((sec_type, title, display_order))
                display_order += 1

        return sections_map, section_metadata
