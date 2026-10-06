"""story_summarizer.py — Editorial Title and Summary Synthesis for Developing Stories."""
import re
import uuid
from typing import Any, List, Optional


class StorySummarizer:
    """Generates concise editorial titles, URL slugs, and synthesized story summaries."""

    @staticmethod
    def generate_slug(title: str, story_id: Optional[uuid.UUID] = None) -> str:
        """Creates a URL-safe slug from title and short UUID suffix."""
        clean = re.sub(r"[^\w\s-]", "", (title or "story").lower())
        slug = re.sub(r"[-\s]+", "-", clean).strip("-")[:80]
        suffix = story_id.hex[:8] if story_id else uuid.uuid4().hex[:8]
        return f"{slug}-{suffix}" if slug else f"story-{suffix}"

    @staticmethod
    def clean_editorial_title(title: str) -> str:
        """Strips sensational prefixes and publisher markers to produce factual editorial headline."""
        if not title:
            return "Developing Story"

        cleaned = title.strip()
        prefixes = [
            r"^(BREAKING|UPDATE|EXCLUSIVE|WATCH|LIVE|JUST IN|ALERT|REPORT|ANALYSIS|OPINION)\s*:\s*",
            r"^\[(BREAKING|UPDATE|EXCLUSIVE|LIVE)\]\s*",
            r"^(Developing Story|Special Report)\s*-\s*",
        ]
        for p in prefixes:
            cleaned = re.sub(p, "", cleaned, flags=re.IGNORECASE).strip()

        # Remove trailing publisher tags (e.g. " - Reuters", " | BBC News", " — TechCrunch")
        cleaned = re.split(r"\s+[-|—]\s+[A-Za-z0-9\s]+$", cleaned)[0].strip()

        return cleaned if len(cleaned) >= 5 else title.strip()

    @classmethod
    def synthesize_story_summary(
        cls,
        articles: List[Any],
        current_summary: Optional[str] = None,
    ) -> str:
        """
        Synthesizes a multi-source story overview from constituent articles without simple duplication.
        Preserves initial core development, key updates, and consensus points.
        """
        if not articles:
            return current_summary or "Developing story with ongoing multi-source coverage."

        # Collect distinct non-empty summaries
        valid_summaries: List[str] = []
        seen_sentences = set()

        for art in articles:
            summary_text = getattr(art, "summary", "") or ""
            if not summary_text:
                analysis = getattr(art, "analysis", None)
                if analysis:
                    summary_text = getattr(analysis, "summary", "") or ""

            if not summary_text:
                continue

            # Break into sentences and deduplicate near-identical sentences
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", summary_text) if len(s.strip()) > 15]
            for sentence in sentences:
                norm = re.sub(r"[^\w\s]", "", sentence.lower())
                if norm not in seen_sentences:
                    seen_sentences.add(norm)
                    valid_summaries.append(sentence)
                if len(valid_summaries) >= 4:
                    break
            if len(valid_summaries) >= 4:
                break

        if valid_summaries:
            return " ".join(valid_summaries[:4])

        # Fallback to article titles / snippet
        first_art = articles[0]
        first_title = getattr(first_art, "title", "Developing story.")
        return f"{first_title} Multiple reports are detailing ongoing developments and reactions."
