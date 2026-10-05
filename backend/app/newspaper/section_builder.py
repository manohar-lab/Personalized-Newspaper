from typing import Dict, List, Optional
from app.core.config import settings
from app.newspaper.editorial_scorer import ScoredCandidateStory
from app.newspaper.schemas import ControlledSection, StoryLayoutType


class SectionBuilder:
    """
    Groups selected candidate stories into controlled sections and assigns layout hierarchy
    (LEAD, FEATURE, STANDARD, COMPACT).
    """

    VALID_SECTIONS = {s.value for s in ControlledSection}

    CATEGORY_MAP = {
        "TECHNOLOGY": ControlledSection.TECHNOLOGY.value,
        "TECH": ControlledSection.TECHNOLOGY.value,
        "AI": ControlledSection.TECHNOLOGY.value,
        "SCIENCE": ControlledSection.SCIENCE.value,
        "BUSINESS": ControlledSection.BUSINESS.value,
        "FINANCE": ControlledSection.BUSINESS.value,
        "ECONOMY": ControlledSection.BUSINESS.value,
        "WORLD": ControlledSection.WORLD.value,
        "POLITICS": ControlledSection.WORLD.value,
        "HEALTH": ControlledSection.HEALTH.value,
        "SPORTS": ControlledSection.SPORTS.value,
        "ENTERTAINMENT": ControlledSection.ENTERTAINMENT.value,
        "CULTURE": ControlledSection.ENTERTAINMENT.value,
    }

    def __init__(
        self,
        max_total_stories: int = settings.NEWSPAPER_MAX_TOTAL_STORIES,
        max_feature_stories: int = settings.NEWSPAPER_FEATURE_STORIES,
        max_standard_stories: int = settings.NEWSPAPER_STANDARD_STORIES,
        max_compact_stories: int = settings.NEWSPAPER_COMPACT_STORIES,
    ):
        self.max_total_stories = max_total_stories
        self.max_feature_stories = max_feature_stories
        self.max_standard_stories = max_standard_stories
        self.max_compact_stories = max_compact_stories

    def map_to_section(self, story: ScoredCandidateStory) -> str:
        """Determines the controlled section for an article."""
        article = story.scored_article.article

        # 1. Primary category check
        if article.primary_category:
            cat_upper = article.primary_category.strip().upper()
            if cat_upper in self.VALID_SECTIONS:
                return cat_upper
            if cat_upper in self.CATEGORY_MAP:
                return self.CATEGORY_MAP[cat_upper]

        # 2. Topic tags check
        if article.topics:
            for topic in article.topics:
                t_name = topic.upper() if isinstance(topic, str) else topic.name.upper()
                if t_name in self.VALID_SECTIONS:
                    return t_name
                if t_name in self.CATEGORY_MAP:
                    return self.CATEGORY_MAP[t_name]

        return ControlledSection.OTHER.value

    def assign_layouts_and_sections(
        self,
        lead_story: Optional[ScoredCandidateStory],
        remaining_stories: List[ScoredCandidateStory],
    ) -> List[dict]:
        """
        Assigns layout_type, section, and position to each story.
        Returns a list of dicts with story attributes ready for persistence.
        """
        assigned_stories: List[dict] = []
        current_position = 1

        # 1. Lead story assignment
        if lead_story:
            lead_section = self.map_to_section(lead_story)
            assigned_stories.append({
                "story": lead_story,
                "section": ControlledSection.TOP_STORIES.value,
                "position": current_position,
                "layout_type": StoryLayoutType.LEAD.value,
                "is_lead": True,
            })
            current_position += 1

        # 2. Limit non-lead stories
        available_slots = max(0, self.max_total_stories - (1 if lead_story else 0))
        selected_stories = remaining_stories[:available_slots]

        # 3. Assign layout types based on ranking order
        feature_count = 0
        standard_count = 0

        for candidate in selected_stories:
            section = self.map_to_section(candidate)

            if feature_count < self.max_feature_stories:
                layout = StoryLayoutType.FEATURE.value
                feature_count += 1
            elif standard_count < self.max_standard_stories:
                layout = StoryLayoutType.STANDARD.value
                standard_count += 1
            else:
                layout = StoryLayoutType.COMPACT.value

            assigned_stories.append({
                "story": candidate,
                "section": section,
                "position": current_position,
                "layout_type": layout,
                "is_lead": False,
            })
            current_position += 1

        return assigned_stories
