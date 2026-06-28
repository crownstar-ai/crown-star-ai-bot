# ====================================================================================================
# life_impact.py – Life Impact Assessment for CrownStar‑Absolute
# Analyzes:
#   - Emotional shift (valence/arousal before/after significant events)
#   - Behavioral changes (extracted from narrative text)
#   - Thematic recurrence (repeating topics, motifs)
#   - Overall impact score
# ====================================================================================================

import time
import re
import math
from typing import List, Dict, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("CrownStar.LifeImpact")

# --------------------------------------------------------------------
# Data classes for impact analysis
# --------------------------------------------------------------------
@dataclass
class EmotionalShift:
    """Change in emotional state before vs after an event."""
    memory_id: str
    event_timestamp: float
    before_valence: float
    after_valence: float
    valence_delta: float
    before_arousal: float
    after_arousal: float
    arousal_delta: float
    significance: float  # 0-1, how statistically significant the shift is
    sample_size_before: int
    sample_size_after: int

@dataclass
class BehavioralChange:
    """A detected change in behavior patterns."""
    memory_id: str
    timestamp: float
    old_behavior: str
    new_behavior: str
    confidence: float
    evidence: str  # snippet from memory

@dataclass
class ThematicRecurrence:
    """A theme that appears multiple times across memories."""
    theme: str
    mention_count: int
    first_mention: float
    last_mention: float
    average_importance: float
    associated_memories: List[str]
    trend: str  # "increasing", "decreasing", "stable"

@dataclass
class ImpactAssessment:
    """Complete impact assessment for a memory or time period."""
    memory_id: str
    timestamp: float
    emotional_impact: float  # 0-1
    behavioral_impact: float
    thematic_impact: float
    overall_impact: float
    emotional_shifts: List[EmotionalShift]
    behavioral_changes: List[BehavioralChange]
    themes: List[str]

# --------------------------------------------------------------------
# Theme extraction (NLP‑light)
# --------------------------------------------------------------------
class ThemeExtractor:
    """Extract themes from text using keyword lists and frequency."""
    
    # Predefined theme keywords (expandable)
    THEME_KEYWORDS = {
        "love": ["love", "loved", "loving", "affection", "care", "cared", "kindness"],
        "fear": ["fear", "afraid", "scared", "terrified", "anxious", "anxiety", "worry"],
        "anger": ["angry", "anger", "frustrated", "frustration", "rage", "annoyed"],
        "sadness": ["sad", "sadness", "depressed", "depression", "grief", "mourning", "lost"],
        "joy": ["joy", "happy", "happiness", "delight", "pleasure", "ecstatic", "wonderful"],
        "achievement": ["achieved", "accomplished", "success", "goal", "completed", "finished", "won"],
        "failure": ["failed", "failure", "mistake", "error", "lost", "defeat"],
        "learning": ["learned", "studied", "understood", "realized", "discovered", "taught"],
        "growth": ["grew", "improved", "progress", "development", "evolved", "matured"],
        "conflict": ["argument", "fight", "disagreement", "conflict", "dispute", "quarrel"],
        "connection": ["connected", "bond", "relationship", "friendship", "together", "united"],
        "loss": ["loss", "lost", "missing", "gone", "passed away", "died", "bereavement"],
        "hope": ["hope", "hopeful", "optimistic", "positive", "looking forward"],
        "regret": ["regret", "wish", "should have", "could have", "would have"],
        "gratitude": ["grateful", "thankful", "appreciate", "blessed", "fortunate"],
        "change": ["changed", "different", "transformed", "shifted", "new", "starting"],
        "work": ["work", "job", "career", "office", "colleague", "boss", "project"],
        "family": ["family", "parent", "child", "sibling", "mother", "father", "daughter", "son"],
        "friends": ["friend", "friendship", "buddy", "pal", "mate", "companion"],
        "health": ["health", "sick", "illness", "disease", "recovery", "healing", "exercise"],
        "travel": ["travel", "trip", "journey", "visited", "tour", "vacation", "holiday"],
        "money": ["money", "finance", "financial", "rich", "poor", "wealth", "income"],
        "spirituality": ["spiritual", "faith", "belief", "prayer", "meditation", "meaning"],
        "creativity": ["creative", "art", "music", "write", "paint", "draw", "compose"],
        "identity": ["identity", "who I am", "self", "purpose", "meaning of life"]
    }
    
    @classmethod
    def extract_themes(cls, text: str, min_confidence: float = 0.3) -> List[Tuple[str, float]]:
        """
        Extract themes from text with confidence scores.
        Returns list of (theme, confidence).
        """
        if not text:
            return []
        text_lower = text.lower()
        themes = []
        for theme, keywords in cls.THEME_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in text_lower)
            if matches > 0:
                confidence = min(1.0, matches / 3.0)  # cap at 1.0
                if confidence >= min_confidence:
                    themes.append((theme, confidence))
        return themes
    
    @classmethod
    def get_theme_summary(cls, memories: List[Dict]) -> Dict[str, int]:
        """Count theme frequencies across a list of memory entries."""
        theme_counts = defaultdict(int)
        for mem in memories:
            text = cls._get_memory_text(mem)
            themes = cls.extract_themes(text, min_confidence=0.4)
            for theme, _ in themes:
                theme_counts[theme] += 1
        return dict(theme_counts)
    
    @classmethod
    def _get_memory_text(cls, memory: Dict) -> str:
        """Extract text from a memory dictionary (supports various formats)."""
        if "narrative" in memory:
            return memory["narrative"]
        if "content" in memory:
            if isinstance(memory["content"], dict):
                return memory["content"].get("query", "") + " " + memory["content"].get("response", "")
            return str(memory["content"])
        if "query" in memory:
            return memory.get("query", "") + " " + memory.get("response", "")
        return ""

# --------------------------------------------------------------------
# Life Impact Assessment Main Class
# --------------------------------------------------------------------
class LifeImpactAssessor:
    """
    Assesses the impact of events (memories) on life trajectory.
    Requires TemporalIndex for time‑based queries and optionally MemoryLibrary for content.
    """
    
    def __init__(self, temporal_index, memory_library=None, xreceptor=None):
        """
        Args:
            temporal_index: TemporalIndex instance for time‑based queries.
            memory_library: Optional MemoryLibrary for retrieving memory content.
            xreceptor: Optional XReceptorEngine for link‑based impact propagation.
        """
        self.temporal_index = temporal_index
        self.memory_library = memory_library
        self.xreceptor = xreceptor
        self.theme_extractor = ThemeExtractor()
        logger.info("LifeImpactAssessor initialised")
    
    def _get_memory_text(self, memory_id: str) -> str:
        """Retrieve the text content of a memory (supports multiple sources)."""
        if self.memory_library:
            book = self.memory_library.get_book(memory_id)
            if book:
                return book.description + " " + " ".join([p.content for p in book.pages[:3]])
        # Fallback: try TemporalIndex metadata
        entry = self.temporal_index._entries.get(memory_id)
        if entry and entry.metadata:
            return entry.metadata.get("description", "") + " " + entry.metadata.get("title", "")
        return ""
    
    def _get_emotional_value(self, memory_id: str) -> Tuple[float, float]:
        """
        Extract valence and arousal from memory metadata.
        Returns (valence, arousal) or (0.5, 0.5) if not available.
        """
        entry = self.temporal_index._entries.get(memory_id)
        if entry and entry.metadata:
            return (entry.metadata.get("valence", 0.5), entry.metadata.get("arousal", 0.5))
        return (0.5, 0.5)
    
    # --------------------------------------------------------------------
    # Emotional Shift Analysis
    # --------------------------------------------------------------------
    def analyze_emotional_shift(self, memory_id: str, window_days: int = 30) -> Optional[EmotionalShift]:
        """
        Compare emotional valence and arousal in the period before vs after a memory.
        Returns an EmotionalShift object, or None if insufficient data.
        """
        entry = self.temporal_index._entries.get(memory_id)
        if not entry:
            return None
        event_time = entry.timestamp
        window_sec = window_days * 86400
        
        # Get memories in before and after windows
        before_memories = self.temporal_index.get_memories_in_range(
            event_time - window_sec, event_time - 1)
        after_memories = self.temporal_index.get_memories_in_range(
            event_time + 1, event_time + window_sec)
        
        if len(before_memories) < 3 or len(after_memories) < 3:
            return None  # insufficient data
        
        # Calculate average valence and arousal before and after
        before_valences = []
        before_arousals = []
        for mid in before_memories:
            v, a = self._get_emotional_value(mid)
            before_valences.append(v)
            before_arousals.append(a)
        after_valences = []
        after_arousals = []
        for mid in after_memories:
            v, a = self._get_emotional_value(mid)
            after_valences.append(v)
            after_arousals.append(a)
        
        avg_before_v = sum(before_valences) / len(before_valences)
        avg_after_v = sum(after_valences) / len(after_valences)
        avg_before_a = sum(before_arousals) / len(before_arousals)
        avg_after_a = sum(after_arousals) / len(after_arousals)
        
        valence_delta = avg_after_v - avg_before_v
        arousal_delta = avg_after_a - avg_before_a
        
        # Compute significance (simplified: based on t‑test approximation)
        # Use effect size (Cohen's d approximation)
        var_before_v = sum((v - avg_before_v)**2 for v in before_valences) / len(before_valences)
        var_after_v = sum((v - avg_after_v)**2 for v in after_valences) / len(after_valences)
        pooled_sd = math.sqrt((var_before_v + var_after_v) / 2)
        effect_size = abs(valence_delta) / (pooled_sd + 1e-6)
        significance = min(1.0, effect_size / 2.0)  # scale: effect 2 -> 1.0
        
        return EmotionalShift(
            memory_id=memory_id,
            event_timestamp=event_time,
            before_valence=avg_before_v,
            after_valence=avg_after_v,
            valence_delta=valence_delta,
            before_arousal=avg_before_a,
            after_arousal=avg_after_a,
            arousal_delta=arousal_delta,
            significance=significance,
            sample_size_before=len(before_memories),
            sample_size_after=len(after_memories)
        )
    
    # --------------------------------------------------------------------
    # Behavioral Change Detection
    # --------------------------------------------------------------------
    def detect_behavioral_changes(self, memory_id: str, window_days: int = 60) -> List[BehavioralChange]:
        """
        Detect behavioral changes mentioned around a memory.
        Uses pattern matching on memory text.
        """
        entry = self.temporal_index._entries.get(memory_id)
        if not entry:
            return []
        event_time = entry.timestamp
        window_sec = window_days * 86400
        
        # Patterns for behavioral changes
        patterns = [
            (r"started (?:to )?(\w+ing)", "started", "new activity"),
            (r"stopped (?:to )?(\w+ing)", "stopped", "ceased activity"),
            (r"began (?:to )?(\w+ing)", "began", "new activity"),
            (r"quit (\w+ing)", "quit", "ceased activity"),
            (r"changed my (job|career|routine|habit)", "changed", "life change"),
            (r"moved to (\w+)", "moved to", "relocation"),
            (r"new (job|position|role)", "new job", "career change"),
            (r"broke up with", "ended relationship", "relationship change"),
            (r"started dating", "started relationship", "relationship change")
        ]
        
        changes = []
        # Look in the memory's own text
        text = self._get_memory_text(memory_id)
        for pattern, change_type, category in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                old_behavior = "unknown"
                new_behavior = match.group(1) if match.groups() else change_type
                changes.append(BehavioralChange(
                    memory_id=memory_id,
                    timestamp=event_time,
                    old_behavior=old_behavior,
                    new_behavior=new_behavior,
                    confidence=0.8,
                    evidence=text[:200]
                ))
        
        # Also check nearby memories (before/after for trend detection)
        nearby = self.temporal_index.get_memories_in_range(
            event_time - window_sec, event_time + window_sec)
        for mid in nearby:
            if mid == memory_id:
                continue
            mem_text = self._get_memory_text(mid)
            for pattern, change_type, category in patterns:
                if re.search(pattern, mem_text, re.IGNORECASE):
                    # If found in a nearby memory, consider as supporting evidence
                    changes.append(BehavioralChange(
                        memory_id=mid,
                        timestamp=self.temporal_index._entries[mid].timestamp,
                        old_behavior="",
                        new_behavior=change_type,
                        confidence=0.6,
                        evidence=mem_text[:200]
                    ))
        return changes
    
    # --------------------------------------------------------------------
    # Thematic Recurrence Analysis
    # --------------------------------------------------------------------
    def analyze_thematic_recurrence(self, memory_id: str, window_days: int = 365) -> List[ThematicRecurrence]:
        """
        Identify themes that recur around a specific memory, and their trends.
        """
        entry = self.temporal_index._entries.get(memory_id)
        if not entry:
            return []
        event_time = entry.timestamp
        window_sec = window_days * 86400
        start_time = event_time - window_sec
        end_time = event_time + window_sec
        
        memories_in_window = self.temporal_index.get_memories_in_range(start_time, end_time)
        # Extract themes for each memory
        themes_over_time = []  # (timestamp, theme, importance)
        for mid in memories_in_window:
            mem_text = self._get_memory_text(mid)
            mem_entry = self.temporal_index._entries.get(mid)
            importance = mem_entry.importance if mem_entry else 0.5
            themes = ThemeExtractor.extract_themes(mem_text, min_confidence=0.4)
            for theme, conf in themes:
                themes_over_time.append((mem_entry.timestamp if mem_entry else event_time, theme, importance * conf))
        
        # Group by theme
        theme_data = defaultdict(list)
        for ts, theme, weight in themes_over_time:
            theme_data[theme].append((ts, weight))
        
        recurrences = []
        for theme, entries in theme_data.items():
            if len(entries) < 2:
                continue
            timestamps = [e[0] for e in entries]
            weights = [e[1] for e in entries]
            first_ts = min(timestamps)
            last_ts = max(timestamps)
            avg_importance = sum(weights) / len(weights)
            # Trend: compare frequency in first half vs second half
            mid_time = (first_ts + last_ts) / 2
            first_half = sum(1 for ts in timestamps if ts < mid_time)
            second_half = sum(1 for ts in timestamps if ts >= mid_time)
            if first_half == 0 and second_half > 0:
                trend = "increasing"
            elif second_half == 0 and first_half > 0:
                trend = "decreasing"
            elif second_half > first_half * 1.5:
                trend = "increasing"
            elif first_half > second_half * 1.5:
                trend = "decreasing"
            else:
                trend = "stable"
            
            recurrences.append(ThematicRecurrence(
                theme=theme,
                mention_count=len(entries),
                first_mention=first_ts,
                last_mention=last_ts,
                average_importance=avg_importance,
                associated_memories=[mid for mid, _ in entries],
                trend=trend
            ))
        
        return sorted(recurrences, key=lambda x: x.mention_count, reverse=True)
    
    # --------------------------------------------------------------------
    # Overall Impact Assessment
    # --------------------------------------------------------------------
    def assess_impact(self, memory_id: str, include_linked: bool = False) -> Optional[ImpactAssessment]:
        """
        Produce a complete impact assessment for a single memory.
        If include_linked is True, also consider memories linked via XReceptor.
        """
        entry = self.temporal_index._entries.get(memory_id)
        if not entry:
            return None
        
        emotional_shift = self.analyze_emotional_shift(memory_id)
        behavioral_changes = self.detect_behavioral_changes(memory_id)
        thematic = self.analyze_thematic_recurrence(memory_id)
        
        # Calculate scores
        emotional_impact = emotional_shift.significance if emotional_shift else 0.0
        behavioral_impact = min(1.0, len(behavioral_changes) * 0.3)
        thematic_impact = min(1.0, len(thematic) * 0.2)
        
        # Combine
        overall = (emotional_impact * 0.4 + behavioral_impact * 0.3 + thematic_impact * 0.3)
        
        # If linked memories exist (via XReceptor), propagate impact
        if include_linked and self.xreceptor:
            linked = self.xreceptor.get_associated_memories(memory_id)
            for linked_id, strength in linked:
                if strength > 0.5:
                    linked_impact = self.assess_impact(linked_id, include_linked=False)
                    if linked_impact:
                        overall = (overall + linked_impact.overall_impact * 0.3) / 1.3
        
        return ImpactAssessment(
            memory_id=memory_id,
            timestamp=entry.timestamp,
            emotional_impact=emotional_impact,
            behavioral_impact=behavioral_impact,
            thematic_impact=thematic_impact,
            overall_impact=overall,
            emotional_shifts=[emotional_shift] if emotional_shift else [],
            behavioral_changes=behavioral_changes,
            themes=[t.theme for t in thematic[:5]]
        )
    
    def assess_period(self, start_time: float, end_time: float) -> Dict[str, Any]:
        """
        Assess the overall impact over a time period.
        Returns aggregated statistics.
        """
        memory_ids = self.temporal_index.get_memories_in_range(start_time, end_time)
        if not memory_ids:
            return {}
        assessments = []
        for mid in memory_ids:
            a = self.assess_impact(mid, include_linked=False)
            if a:
                assessments.append(a)
        if not assessments:
            return {}
        avg_emotional = sum(a.emotional_impact for a in assessments) / len(assessments)
        avg_behavioral = sum(a.behavioral_impact for a in assessments) / len(assessments)
        avg_thematic = sum(a.thematic_impact for a in assessments) / len(assessments)
        avg_overall = sum(a.overall_impact for a in assessments) / len(assessments)
        # Collect all themes
        all_themes = Counter()
        for a in assessments:
            for theme in a.themes:
                all_themes[theme] += 1
        return {
            "period_start": start_time,
            "period_end": end_time,
            "memory_count": len(memory_ids),
            "assessed_count": len(assessments),
            "average_emotional_impact": avg_emotional,
            "average_behavioral_impact": avg_behavioral,
            "average_thematic_impact": avg_thematic,
            "average_overall_impact": avg_overall,
            "top_themes": all_themes.most_common(5),
            "most_impactful_memory": max(assessments, key=lambda a: a.overall_impact).memory_id if assessments else None
        }
    
    # --------------------------------------------------------------------
    # High‑level report generation
    # --------------------------------------------------------------------
    def generate_impact_report(self, memory_id: str) -> str:
        """
        Generate a human‑readable impact report for a memory.
        """
        assessment = self.assess_impact(memory_id, include_linked=True)
        if not assessment:
            return f"No assessment available for memory {memory_id}"
        
        dt = datetime.fromtimestamp(assessment.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"IMPACT ASSESSMENT for memory {memory_id[:8]}",
            f"Timestamp: {dt}",
            f"Overall Impact Score: {assessment.overall_impact:.3f}",
            f"  - Emotional Impact: {assessment.emotional_impact:.3f}",
            f"  - Behavioral Impact: {assessment.behavioral_impact:.3f}",
            f"  - Thematic Impact: {assessment.thematic_impact:.3f}",
            ""
        ]
        if assessment.emotional_shifts:
            es = assessment.emotional_shifts[0]
            lines.append(f"Emotional Shift: valence {es.before_valence:.2f} → {es.after_valence:.2f} (Δ={es.valence_delta:+.2f})")
            lines.append(f"                    arousal {es.before_arousal:.2f} → {es.after_arousal:.2f} (Δ={es.arousal_delta:+.2f})")
        if assessment.behavioral_changes:
            lines.append(f"Behavioral Changes detected: {len(assessment.behavioral_changes)}")
            for bc in assessment.behavioral_changes[:3]:
                lines.append(f"  - {bc.new_behavior} (conf={bc.confidence:.2f})")
        if assessment.themes:
            lines.append(f"Dominant themes: {', '.join(assessment.themes[:5])}")
        return "\n".join(lines)

# --------------------------------------------------------------------
# Example usage (commented)
# --------------------------------------------------------------------
"""
# Assuming temporal_index and memory_library are set up
assessor = LifeImpactAssessor(temporal_index, memory_library, xreceptor)

# Assess a single memory
impact = assessor.assess_impact("mem_123")
if impact:
    print(f"Overall impact: {impact.overall_impact}")

# Generate report
print(assessor.generate_impact_report("mem_123"))

# Assess a time period
period_impact = assessor.assess_period(
    start_time=datetime(2024,1,1).timestamp(),
    end_time=datetime(2024,12,31).timestamp()
)
print(f"Average impact in 2024: {period_impact['average_overall_impact']}")
"""

# ====================================================================================================
# END OF life_impact.py (32,491 characters)
# ====================================================================================================
