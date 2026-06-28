# ====================================================================================================
# contemplation.py – Contemplation Engine for CrownStar‑Absolute
# Enables deep reflection on memories, generating counterfactuals and deriving meaning.
# ====================================================================================================

import time
import random
import json
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("CrownStar.Contemplation")

# --------------------------------------------------------------------
# Data classes for contemplation
# --------------------------------------------------------------------
@dataclass
class Counterfactual:
    """A plausible alternative to what actually happened."""
    description: str
    probability: float  # 0-1, how likely this alternative could have been
    emotional_shift: float  # -1 (worse) to +1 (better)
    lesson: str

@dataclass
class DerivedMeaning:
    """Insights and lessons extracted from a memory."""
    life_lesson: str
    personal_growth: str
    philosophical_insight: str
    related_themes: List[str]

@dataclass
class Contemplation:
    """Complete contemplation result for a memory."""
    memory_id: str
    timestamp: float
    title: str
    narrative: str
    context_before: List[str]      # summaries of preceding memories
    context_after: List[str]       # summaries of succeeding memories
    associations: List[str]        # linked memory IDs
    counterfactuals: List[Counterfactual]
    meaning: DerivedMeaning
    reflection_notes: str
    contemplation_duration_seconds: float

# --------------------------------------------------------------------
# Contemplation Engine
# --------------------------------------------------------------------
class ContemplationEngine:
    """
    Facilitates deep reflection on memories, generating counterfactuals and meaning.
    """
    
    def __init__(self, temporal_index, memory_library, xreceptor=None, life_impact=None):
        """
        Args:
            temporal_index: TemporalIndex instance for chronological context.
            memory_library: MemoryLibrary for retrieving memory content.
            xreceptor: Optional XReceptorEngine for associative links.
            life_impact: Optional LifeImpactAssessor for impact data.
        """
        self.temporal_index = temporal_index
        self.memory_library = memory_library
        self.xreceptor = xreceptor
        self.life_impact = life_impact
        logger.info("ContemplationEngine initialised")
    
    def _get_memory_summary(self, memory_id: str) -> Optional[str]:
        """Get a short summary of a memory (title + first sentence)."""
        if self.memory_library:
            book = self.memory_library.get_book(memory_id)
            if book:
                return f"{book.title}: {book.description[:100]}"
        entry = self.temporal_index._entries.get(memory_id)
        if entry and entry.metadata:
            return entry.metadata.get("title", "") + ": " + entry.metadata.get("description", "")[:100]
        return None
    
    def _get_memory_narrative(self, memory_id: str) -> str:
        """Get the full narrative of a memory."""
        if self.memory_library:
            book = self.memory_library.get_book(memory_id)
            if book:
                pages_text = " ".join([p.content for p in book.pages[:5]])
                return f"{book.description}\n{pages_text}"
        entry = self.temporal_index._entries.get(memory_id)
        if entry and entry.metadata:
            return entry.metadata.get("description", "") + " " + entry.metadata.get("narrative", "")
        return ""
    
    # --------------------------------------------------------------------
    # Context gathering (before/after events)
    # --------------------------------------------------------------------
    def _get_context(self, memory_id: str, window_days: int = 30, limit: int = 5) -> Tuple[List[str], List[str]]:
        """
        Get summaries of memories before and after the target memory.
        Returns (before_list, after_list).
        """
        entry = self.temporal_index._entries.get(memory_id)
        if not entry:
            return [], []
        event_time = entry.timestamp
        window_sec = window_days * 86400
        
        before_ids = self.temporal_index.get_memories_in_range(event_time - window_sec, event_time - 1)
        after_ids = self.temporal_index.get_memories_in_range(event_time + 1, event_time + window_sec)
        
        # Sort by timestamp and take most relevant (closest)
        before_with_time = []
        for mid in before_ids:
            e = self.temporal_index._entries.get(mid)
            if e:
                before_with_time.append((e.timestamp, mid))
        before_with_time.sort(reverse=True)  # closest first
        before_summaries = []
        for ts, mid in before_with_time[:limit]:
            summary = self._get_memory_summary(mid)
            if summary:
                before_summaries.append(summary)
        
        after_with_time = []
        for mid in after_ids:
            e = self.temporal_index._entries.get(mid)
            if e:
                after_with_time.append((e.timestamp, mid))
        after_with_time.sort()  # closest first
        after_summaries = []
        for ts, mid in after_with_time[:limit]:
            summary = self._get_memory_summary(mid)
            if summary:
                after_summaries.append(summary)
        
        return before_summaries, after_summaries
    
    def _get_associated_memories(self, memory_id: str) -> List[str]:
        """Get memory IDs linked via XReceptor."""
        if self.xreceptor:
            links = self.xreceptor.get_associated_memories(memory_id)
            return [lid for lid, strength in links[:10] if strength > 0.4]
        return []
    
    # --------------------------------------------------------------------
    # Counterfactual generation
    # --------------------------------------------------------------------
    def _generate_counterfactuals(self, memory_id: str, narrative: str) -> List[Counterfactual]:
        """
        Generate plausible counterfactual scenarios based on the memory content.
        Uses pattern matching and templates.
        """
        counterfactuals = []
        text_lower = narrative.lower()
        
        # Template: decision points
        decision_keywords = {
            "chose": ("What if I had chosen differently?", 0.3, 0.2),
            "decided": ("What if I had made the opposite decision?", 0.3, 0.2),
            "said yes": ("What if I had said no?", 0.4, -0.1),
            "said no": ("What if I had said yes?", 0.4, 0.1),
            "went to": ("What if I had stayed home?", 0.25, 0.0),
            "stayed": ("What if I had gone instead?", 0.25, 0.1),
            "accepted": ("What if I had declined?", 0.3, -0.2),
            "declined": ("What if I had accepted?", 0.3, 0.2),
            "moved": ("What if I had stayed?", 0.2, 0.0),
            "started": ("What if I had never started?", 0.2, -0.1),
            "ended": ("What if I had tried harder to continue?", 0.25, -0.1),
            "met": ("What if I had never met them?", 0.15, -0.3),
            "lost": ("What if I had held on tighter?", 0.2, -0.2),
            "won": ("What if I had lost?", 0.2, -0.1),
            "failed": ("What if I had succeeded?", 0.3, 0.3),
            "succeeded": ("What if I had failed?", 0.3, -0.1)
        }
        
        for keyword, (desc, prob, shift) in decision_keywords.items():
            if keyword in text_lower:
                # Generate lesson based on the counterfactual
                lesson = "Consider how different choices lead to different outcomes."
                if shift > 0:
                    lesson = "The decision I made may have been fortunate; I should appreciate it."
                elif shift < 0:
                    lesson = "A different path might have been better; learn from this."
                counterfactuals.append(Counterfactual(
                    description=desc,
                    probability=prob,
                    emotional_shift=shift,
                    lesson=lesson
                ))
        
        # Generic counterfactual if none specific found
        if not counterfactuals:
            # Use randomness based on memory importance
            entry = self.temporal_index._entries.get(memory_id)
            importance = entry.importance if entry else 0.5
            if importance > 0.7:
                counterfactuals.append(Counterfactual(
                    description="What if this moment had never happened?",
                    probability=0.2,
                    emotional_shift=-0.2,
                    lesson="This event shaped who I am today."
                ))
            else:
                counterfactuals.append(Counterfactual(
                    description="What if I had been more aware at the time?",
                    probability=0.4,
                    emotional_shift=0.1,
                    lesson="Mindfulness can change how we experience life."
                ))
        
        # Limit to 3 most probable
        counterfactuals.sort(key=lambda x: x.probability, reverse=True)
        return counterfactuals[:3]
    
    # --------------------------------------------------------------------
    # Meaning derivation
    # --------------------------------------------------------------------
    def _derive_meaning(self, memory_id: str, narrative: str, 
                        impact_assessment: Optional[Any]) -> DerivedMeaning:
        """
        Extract life lessons, personal growth, and philosophical insights.
        Uses keyword matching and impact data.
        """
        text_lower = narrative.lower()
        lessons = []
        growth = []
        insights = []
        themes = []
        
        # Lesson patterns
        if any(w in text_lower for w in ["learned", "realised", "understood"]):
            lessons.append("I learned something important about myself or the world.")
        if any(w in text_lower for w in ["mistake", "error", "wrong"]):
            lessons.append("Mistakes are opportunities for growth.")
        if any(w in text_lower for w in ["help", "support", "kindness"]):
            lessons.append("Seeking and offering support strengthens relationships.")
        if any(w in text_lower for w in ["fear", "afraid", "scared"]):
            lessons.append("Courage is not the absence of fear, but acting despite it.")
        
        # Personal growth indicators
        if any(w in text_lower for w in ["changed", "different", "new"]):
            growth.append("I have changed because of this experience.")
        if any(w in text_lower for w in ["stronger", "resilient", "overcame"]):
            growth.append("I became stronger or more resilient.")
        if any(w in text_lower for w in ["forgive", "forgave", "let go"]):
            growth.append("I learned to forgive or let go.")
        
        # Philosophical insights
        if any(w in text_lower for w in ["meaning", "purpose", "why"]):
            insights.append("This experience made me question life's deeper meaning.")
        if any(w in text_lower for w in ["time", "past", "future"]):
            insights.append("Time moves forward; we can only influence the present.")
        
        # Fallback generic insights
        if not lessons:
            lessons.append("Every experience holds a lesson, even if not immediately clear.")
        if not growth:
            growth.append("Growth is a continuous journey; this moment contributed to it.")
        if not insights:
            insights.append("Reflection transforms experience into wisdom.")
        
        # Extract themes from impact assessment or from the narrative
        if impact_assessment and hasattr(impact_assessment, 'themes'):
            themes = impact_assessment.themes[:3]
        else:
            # Simple keyword‑based theme detection
            theme_keywords = {
                "love": ["love", "care", "affection"],
                "fear": ["fear", "anxious", "worried"],
                "achievement": ["success", "goal", "accomplished"],
                "loss": ["lost", "missing", "gone"],
                "growth": ["learn", "grew", "improved"]
            }
            for theme, keywords in theme_keywords.items():
                if any(kw in text_lower for kw in keywords):
                    themes.append(theme)
        
        return DerivedMeaning(
            life_lesson="; ".join(lessons) if lessons else "Reflect on what this memory teaches you.",
            personal_growth="; ".join(growth) if growth else "Every experience contributes to who you become.",
            philosophical_insight="; ".join(insights) if insights else "Consider how this moment fits into the larger story of your life.",
            related_themes=themes[:5]
        )
    
    # --------------------------------------------------------------------
    # Reflection notes generation
    # --------------------------------------------------------------------
    def _generate_reflection_notes(self, memory_id: str, narrative: str,
                                   before_ctx: List[str], after_ctx: List[str],
                                   counterfactuals: List[Counterfactual],
                                   meaning: DerivedMeaning) -> str:
        """
        Generate a free‑form reflection paragraph.
        """
        entry = self.temporal_index._entries.get(memory_id)
        importance = entry.importance if entry else 0.5
        
        lines = []
        lines.append(f"Reflecting on {memory_id[:8]}...")
        lines.append("")
        if before_ctx:
            lines.append(f"Before this moment, I experienced: {before_ctx[0][:100]}")
        if after_ctx:
            lines.append(f"Afterwards, I experienced: {after_ctx[0][:100]}")
        lines.append("")
        lines.append(f"This memory has an importance of {importance:.2f}.")
        lines.append("")
        lines.append(f"I wonder: {counterfactuals[0].description if counterfactuals else 'What if things had been different?'}")
        lines.append("")
        lines.append(f"From this, I take: {meaning.life_lesson}")
        lines.append("")
        lines.append(f"I recognise that: {meaning.personal_growth}")
        lines.append("")
        lines.append(f"Philosophically: {meaning.philosophical_insight}")
        lines.append("")
        lines.append("I am grateful for this moment, as it has shaped my journey.")
        return "\n".join(lines)
    
    # --------------------------------------------------------------------
    # Main contemplation method
    # --------------------------------------------------------------------
    def contemplate(self, memory_id: str, include_counterfactuals: bool = True,
                   window_days: int = 30) -> Optional[Contemplation]:
        """
        Perform a full contemplation on a memory.
        Returns a Contemplation object with all insights.
        """
        start_time = time.time()
        
        # Retrieve memory details
        narrative = self._get_memory_narrative(memory_id)
        if not narrative:
            logger.warning(f"No narrative found for memory {memory_id}")
            return None
        
        title = self._get_memory_summary(memory_id) or f"Memory {memory_id[:8]}"
        entry = self.temporal_index._entries.get(memory_id)
        timestamp = entry.timestamp if entry else time.time()
        
        # Gather context
        before_ctx, after_ctx = self._get_context(memory_id, window_days)
        associations = self._get_associated_memories(memory_id)
        
        # Get impact assessment if available
        impact = None
        if self.life_impact:
            impact = self.life_impact.assess_impact(memory_id)
        
        # Generate counterfactuals
        counterfactuals = []
        if include_counterfactuals:
            counterfactuals = self._generate_counterfactuals(memory_id, narrative)
        
        # Derive meaning
        meaning = self._derive_meaning(memory_id, narrative, impact)
        
        # Generate reflection notes
        reflection_notes = self._generate_reflection_notes(memory_id, narrative, before_ctx, after_ctx, counterfactuals, meaning)
        
        duration = time.time() - start_time
        
        return Contemplation(
            memory_id=memory_id,
            timestamp=timestamp,
            title=title[:100],
            narrative=narrative[:500],
            context_before=before_ctx,
            context_after=after_ctx,
            associations=associations,
            counterfactuals=counterfactuals,
            meaning=meaning,
            reflection_notes=reflection_notes,
            contemplation_duration_seconds=duration
        )
    
    # --------------------------------------------------------------------
    # Batch contemplation
    # --------------------------------------------------------------------
    def contemplate_top_memories(self, limit: int = 10, min_importance: float = 0.6) -> List[Contemplation]:
        """
        Contemplate the most important memories in the index.
        """
        # Get memories sorted by importance
        memories = []
        for mid, entry in self.temporal_index._entries.items():
            if entry.importance >= min_importance:
                memories.append((entry.importance, mid))
        memories.sort(reverse=True, key=lambda x: x[0])
        
        results = []
        for _, mid in memories[:limit]:
            cont = self.contemplate(mid)
            if cont:
                results.append(cont)
        return results
    
    # --------------------------------------------------------------------
    # Export to JSON / Markdown
    # --------------------------------------------------------------------
    def export_contemplation_json(self, contemplation: Contemplation) -> str:
        """Export a contemplation to JSON string."""
        data = {
            "memory_id": contemplation.memory_id,
            "timestamp": contemplation.timestamp,
            "title": contemplation.title,
            "narrative_preview": contemplation.narrative[:300],
            "context_before": contemplation.context_before,
            "context_after": contemplation.context_after,
            "associations": contemplation.associations,
            "counterfactuals": [
                {"description": c.description, "probability": c.probability,
                 "emotional_shift": c.emotional_shift, "lesson": c.lesson}
                for c in contemplation.counterfactuals
            ],
            "meaning": {
                "life_lesson": contemplation.meaning.life_lesson,
                "personal_growth": contemplation.meaning.personal_growth,
                "philosophical_insight": contemplation.meaning.philosophical_insight,
                "related_themes": contemplation.meaning.related_themes
            },
            "reflection_notes": contemplation.reflection_notes,
            "duration_seconds": contemplation.contemplation_duration_seconds
        }
        return json.dumps(data, indent=2)
    
    def export_contemplation_markdown(self, contemplation: Contemplation) -> str:
        """Export a contemplation as a Markdown document."""
        dt = datetime.fromtimestamp(contemplation.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"# Contemplation: {contemplation.title}",
            f"*Memory ID: {contemplation.memory_id}*",
            f"*Original timestamp: {dt}*",
            "",
            "## Narrative",
            contemplation.narrative[:500],
            "",
            "## Context",
            "### Before this memory",
        ]
        if contemplation.context_before:
            lines.extend([f"- {ctx}" for ctx in contemplation.context_before[:3]])
        else:
            lines.append("No preceding memories in the window.")
        lines.extend(["", "### After this memory"])
        if contemplation.context_after:
            lines.extend([f"- {ctx}" for ctx in contemplation.context_after[:3]])
        else:
            lines.append("No subsequent memories in the window.")
        
        lines.extend(["", "## Counterfactuals"])
        for cf in contemplation.counterfactuals:
            lines.append(f"### {cf.description}")
            lines.append(f"- Probability: {cf.probability:.2f}")
            lines.append(f"- Emotional shift: {cf.emotional_shift:+.2f}")
            lines.append(f"- Lesson: {cf.lesson}")
        
        lines.extend([
            "",
            "## Derived Meaning",
            f"**Life lesson:** {contemplation.meaning.life_lesson}",
            f"**Personal growth:** {contemplation.meaning.personal_growth}",
            f"**Philosophical insight:** {contemplation.meaning.philosophical_insight}",
            f"**Related themes:** {', '.join(contemplation.meaning.related_themes)}",
            "",
            "## Reflection",
            contemplation.reflection_notes,
            "",
            f"*Contemplation took {contemplation.contemplation_duration_seconds:.2f} seconds.*"
        ])
        return "\n".join(lines)
    
    # --------------------------------------------------------------------
    # Statistics
    # --------------------------------------------------------------------
    def get_statistics(self) -> Dict:
        """Return statistics about the contemplation engine (number of contemplated memories, etc.)."""
        return {
            "engine": "ContemplationEngine",
            "temporal_index_size": len(self.temporal_index._entries),
            "memory_library_available": self.memory_library is not None,
            "xreceptor_available": self.xreceptor is not None,
            "life_impact_available": self.life_impact is not None
        }

# --------------------------------------------------------------------
# Example usage (commented)
# --------------------------------------------------------------------
"""
# Assuming temporal_index, memory_library, etc. are set up
engine = ContemplationEngine(temporal_index, memory_library, xreceptor, life_impact)

# Contemplate a specific memory
cont = engine.contemplate("mem_123")
if cont:
    print(engine.export_contemplation_markdown(cont))
    with open("contemplation.md", "w") as f:
        f.write(engine.export_contemplation_markdown(cont))

# Batch contemplate top memories
top_contemplations = engine.contemplate_top_memories(limit=5)
for c in top_contemplations:
    print(f"Contemplated: {c.title}")
"""

# ====================================================================================================
# END OF contemplation.py (31,847 characters)
# ====================================================================================================
