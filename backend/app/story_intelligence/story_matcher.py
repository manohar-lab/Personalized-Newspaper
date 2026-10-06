"""story_matcher.py — Phase 16 Story Matching & Relationship Classification."""
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.config import settings
from app.personalization.scoring.semantic_scorer import SemanticScorer


class StoryMatcher:
    """Calculates multi-dimensional match scores between articles and stories."""

    def __init__(
        self,
        match_threshold: float = settings.STORY_MATCH_THRESHOLD,
        semantic_weight: float = settings.STORY_SEMANTIC_WEIGHT,
        entity_weight: float = settings.STORY_ENTITY_WEIGHT,
        topic_weight: float = settings.STORY_TOPIC_WEIGHT,
        keyword_weight: float = settings.STORY_KEYWORD_WEIGHT,
        temporal_weight: float = settings.STORY_TEMPORAL_WEIGHT,
        title_weight: float = settings.STORY_TITLE_WEIGHT,
        window_days: int = settings.STORY_WINDOW_DAYS,
    ):
        self.match_threshold = match_threshold
        self.semantic_weight = semantic_weight
        self.entity_weight = entity_weight
        self.topic_weight = topic_weight
        self.keyword_weight = keyword_weight
        self.temporal_weight = temporal_weight
        self.title_weight = title_weight
        self.window_days = max(1, window_days)

    @staticmethod
    def _get_title_tokens(title: Optional[str]) -> Set[str]:
        if not title:
            return set()
        words = re.findall(r"\b[a-zA-Z0-9]{3,}\b", title.lower())
        stopwords = {
            "the", "and", "for", "with", "from", "that", "this", "after",
            "into", "over", "about", "new", "says", "will", "how", "what",
            "why", "who", "when", "more", "most", "some", "first", "also",
        }
        return set(w for w in words if w not in stopwords)

    @staticmethod
    def _extract_entity_names(obj: Any) -> Set[str]:
        entities = set()
        if not obj:
            return entities
        # If object has entities attribute (e.g. Article)
        raw_entities = getattr(obj, "entities", None)
        if raw_entities:
            for ent in raw_entities:
                name = getattr(ent, "name", None) or (ent.get("name") if isinstance(ent, dict) else str(ent))
                if name:
                    entities.add(name.lower().strip())
        return entities

    @staticmethod
    def _extract_keywords(obj: Any) -> Set[str]:
        keywords = set()
        if not obj:
            return keywords
        raw_kw = getattr(obj, "keywords", None)
        if raw_kw:
            for kw in raw_kw:
                word = getattr(kw, "keyword", None) or (kw.get("keyword") if isinstance(kw, dict) else str(kw))
                if word:
                    keywords.add(word.lower().strip())
        return keywords

    @staticmethod
    def _extract_topics(obj: Any) -> Set[str]:
        topics = set()
        if not obj:
            return topics
        raw_top = getattr(obj, "topics", None)
        if raw_top:
            for t in raw_top:
                slug = getattr(t, "slug", None) or getattr(t, "name", None) or (t.get("slug") if isinstance(t, dict) else str(t))
                if slug:
                    topics.add(slug.lower().strip())
        return topics

    @staticmethod
    def _get_embedding(obj: Any) -> Optional[List[float]]:
        if not obj:
            return None
        analysis = getattr(obj, "analysis", None)
        if analysis and getattr(analysis, "embedding", None):
            return analysis.embedding
        if hasattr(obj, "embedding") and obj.embedding:
            return obj.embedding
        return None

    def compute_temporal_proximity(
        self, article_time: Optional[datetime], story_time: Optional[datetime]
    ) -> float:
        """Exponential decay based on time difference in days."""
        if not article_time or not story_time:
            return 0.5
        if article_time.tzinfo is None:
            article_time = article_time.replace(tzinfo=timezone.utc)
        if story_time.tzinfo is None:
            story_time = story_time.replace(tzinfo=timezone.utc)

        delta_days = abs((article_time - story_time).total_seconds()) / 86400.0
        return float(math.exp(-delta_days / float(self.window_days)))

    def compute_match_score(
        self,
        article: Any,
        story: Any,
        story_primary_article: Optional[Any] = None,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculates normalized composite match score (0.0 - 1.0) and breakdown.
        """
        # 1. Semantic Similarity
        art_emb = self._get_embedding(article)
        story_emb = self._get_embedding(story_primary_article) or self._get_embedding(story)
        sem_score = 0.0
        if art_emb and story_emb:
            cos = SemanticScorer.cosine_similarity(art_emb, story_emb)
            sem_score = max(0.0, min(1.0, cos))

        # 2. Entity Overlap (Jaccard)
        art_ents = self._extract_entity_names(article)
        story_ents = self._extract_entity_names(story_primary_article) | self._extract_entity_names(story)
        ent_score = 0.0
        if art_ents and story_ents:
            inter = len(art_ents & story_ents)
            union = len(art_ents | story_ents)
            ent_score = inter / union if union > 0 else 0.0

        # 3. Topic Overlap
        art_topics = self._extract_topics(article)
        story_topics = self._extract_topics(story_primary_article) | self._extract_topics(story)
        if getattr(story, "primary_topic_id", None):
            story_topics.add(str(story.primary_topic_id))
        top_score = 0.0
        if art_topics and story_topics:
            inter = len(art_topics & story_topics)
            union = len(art_topics | story_topics)
            top_score = inter / union if union > 0 else 0.0

        # 4. Keyword Overlap
        art_kw = self._extract_keywords(article)
        story_kw = self._extract_keywords(story_primary_article) | self._extract_keywords(story)
        kw_score = 0.0
        if art_kw and story_kw:
            inter = len(art_kw & story_kw)
            union = len(art_kw | story_kw)
            kw_score = inter / union if union > 0 else 0.0

        # 5. Temporal Proximity
        art_pub = getattr(article, "published_at", None) or getattr(article, "created_at", None)
        story_pub = getattr(story, "last_updated_at", None) or getattr(story, "first_published_at", None)
        temp_score = self.compute_temporal_proximity(art_pub, story_pub)

        # 6. Title Similarity (Jaccard)
        art_title = getattr(article, "title", "") or ""
        story_title = getattr(story, "title", "") or getattr(story_primary_article, "title", "") or ""
        art_tokens = self._get_title_tokens(art_title)
        story_tokens = self._get_title_tokens(story_title)
        title_score = 0.0
        if art_tokens and story_tokens:
            inter = len(art_tokens & story_tokens)
            union = len(art_tokens | story_tokens)
            title_score = inter / union if union > 0 else 0.0

        # Handle case where embeddings are missing (boost lexical & entity signals)
        if not art_emb or not story_emb:
            adj_ent_weight = self.entity_weight + 0.15
            adj_title_weight = self.title_weight + 0.15
            adj_topic_weight = self.topic_weight + 0.05
            composite = (
                adj_ent_weight * ent_score
                + adj_title_weight * title_score
                + adj_topic_weight * top_score
                + self.keyword_weight * kw_score
                + self.temporal_weight * temp_score
            )
        else:
            composite = (
                self.semantic_weight * sem_score
                + self.entity_weight * ent_score
                + self.topic_weight * top_score
                + self.keyword_weight * kw_score
                + self.temporal_weight * temp_score
                + self.title_weight * title_score
            )

        # Boost score if title token overlap, semantic similarity, or entity overlap is very strong
        if sem_score >= 0.85:
            composite = max(composite, 0.75 + (sem_score - 0.85) * 0.8)
        elif sem_score >= 0.75 and (title_score >= 0.20 or ent_score >= 0.20):
            composite = max(composite, 0.68)
        elif title_score >= 0.50 and ent_score >= 0.30:
            composite = max(composite, 0.75)
        elif title_score >= 0.60:
            composite = max(composite, 0.70)
        elif title_score >= 0.35 and temp_score >= 0.80 and ent_score >= 0.20:
            composite = max(composite, 0.65)


        composite = round(max(0.0, min(1.0, composite)), 4)
        breakdown = {
            "semantic": sem_score,
            "entity": ent_score,
            "topic": top_score,
            "keyword": kw_score,
            "temporal": temp_score,
            "title": title_score,
            "composite": composite,
        }
        return composite, breakdown

    def classify_relationship(
        self,
        article: Any,
        story: Any,
        is_first: bool = False,
    ) -> str:
        """
        Classifies relationship of article to the story:
        PRIMARY | UPDATE | ANALYSIS | REACTION | BACKGROUND | RELATED
        """
        if is_first:
            return "PRIMARY"

        title_lower = (getattr(article, "title", "") or "").lower()
        content_lower = ((getattr(article, "content", "") or "")[:500]).lower()
        combined = f"{title_lower} {content_lower}"

        # Reaction indicators
        reaction_patterns = [
            "reacts", "reaction", "criticizes", "praises", "condemns",
            "slams", "welcomes", "statement on", "speaks out", "responds to",
            "pushback", "calls for",
        ]
        if any(p in combined for p in reaction_patterns):
            return "REACTION"

        # Analysis indicators
        analysis_patterns = [
            "analysis", "opinion", "what it means", "explainer", "why it matters",
            "perspective", "breakdown", "column", "editorial", "deep dive",
            "look inside", "future of",
        ]
        if any(p in combined for p in analysis_patterns):
            return "ANALYSIS"

        # Background indicators
        background_patterns = [
            "timeline of", "history of", "background on", "how we got here",
            "everything you need to know",
        ]
        if any(p in combined for p in background_patterns):
            return "BACKGROUND"

        # Update vs Related
        art_pub = getattr(article, "published_at", None)
        story_pub = getattr(story, "first_published_at", None)
        if art_pub and story_pub:
            if art_pub.tzinfo is None:
                art_pub = art_pub.replace(tzinfo=timezone.utc)
            if story_pub.tzinfo is None:
                story_pub = story_pub.replace(tzinfo=timezone.utc)
            if (art_pub - story_pub).total_seconds() > 3600:  # > 1 hour after first report
                return "UPDATE"

        return "UPDATE"
