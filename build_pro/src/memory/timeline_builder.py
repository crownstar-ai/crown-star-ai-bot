# ====================================================================================================
# timeline_builder.py – Timeline Builder for CrownStar‑Absolute
# Constructs chronological timelines from TemporalIndex, with grouping, filtering,
# narrative generation, and export to multiple formats.
# ====================================================================================================

import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logger = logging.getLogger("CrownStar.TimelineBuilder")

# --------------------------------------------------------------------
# Timeline Event (single point)
# --------------------------------------------------------------------
@dataclass
class TimelineEvent:
    """A single event on a timeline (wraps a memory)."""
    memory_id: str
    timestamp: float
    title: str
    description: str = ""
    importance: float = 0.5
    phase: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp)
    
    def to_dict(self) -> Dict:
        return {
            "memory_id": self.memory_id,
            "timestamp": self.timestamp,
            "title": self.title,
            "description": self.description,
            "importance": self.importance,
            "phase": self.phase,
            "tags": self.tags,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_memory_entry(cls, memory_id: str, timestamp: float, importance: float,
                          metadata: Dict = None) -> 'TimelineEvent':
        meta = metadata or {}
        return cls(
            memory_id=memory_id,
            timestamp=timestamp,
            title=meta.get("title", f"Memory {memory_id[:8]}"),
            description=meta.get("description", ""),
            importance=importance,
            phase=meta.get("phase", ""),
            tags=meta.get("tags", []),
            metadata=meta
        )

# --------------------------------------------------------------------
# Timeline Segment (continuous period)
# --------------------------------------------------------------------
@dataclass
class TimelineSegment:
    """A segment of timeline (e.g., a year, a life phase)."""
    start_time: float
    end_time: float
    events: List[TimelineEvent]
    title: str = ""
    description: str = ""
    
    @property
    def duration_days(self) -> float:
        return (self.end_time - self.start_time) / 86400
    
    @property
    def event_count(self) -> int:
        return len(self.events)
    
    def get_most_important_events(self, limit: int = 3) -> List[TimelineEvent]:
        """Return the most important events in this segment."""
        sorted_events = sorted(self.events, key=lambda e: e.importance, reverse=True)
        return sorted_events[:limit]
    
    def to_dict(self) -> Dict:
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "events": [e.to_dict() for e in self.events],
            "title": self.title,
            "description": self.description
        }

# --------------------------------------------------------------------
# Main Timeline Builder
# --------------------------------------------------------------------
class TimelineBuilder:
    """
    Builds timelines from a TemporalIndex, supporting grouping by year, month,
    life phase, or custom intervals.
    """
    
    def __init__(self, temporal_index, memory_library=None):
        """
        Args:
            temporal_index: TemporalIndex instance.
            memory_library: Optional MemoryLibrary for enriching event data.
        """
        self.temporal_index = temporal_index
        self.memory_library = memory_library
        logger.info("TimelineBuilder initialised")
    
    def _enrich_event(self, memory_id: str, timestamp: float, importance: float,
                      metadata: Dict = None) -> TimelineEvent:
        """Create a TimelineEvent, optionally enriching from MemoryLibrary."""
        if self.memory_library:
            book = self.memory_library.get_book(memory_id)
            if book:
                return TimelineEvent(
                    memory_id=memory_id,
                    timestamp=timestamp,
                    title=book.title,
                    description=book.description,
                    importance=importance,
                    phase=metadata.get("phase", "") if metadata else "",
                    tags=book.subjects,
                    metadata={"author": book.author, "pages": len(book.pages)}
                )
        # Fallback
        return TimelineEvent.from_memory_entry(memory_id, timestamp, importance, metadata)
    
    # --------------------------------------------------------------------
    # Build full timeline
    # --------------------------------------------------------------------
    def build_full_timeline(self, start_time: Optional[float] = None,
                           end_time: Optional[float] = None,
                           min_importance: float = 0.0) -> List[TimelineEvent]:
        """
        Build a flat list of all events in chronological order (optionally filtered).
        """
        if start_time is None:
            start_time = 0
        if end_time is None:
            end_time = float('inf')
        memory_ids = self.temporal_index.get_memories_in_range(start_time, end_time)
        events = []
        for mid in memory_ids:
            entry = self.temporal_index._entries.get(mid)
            if entry and entry.importance >= min_importance:
                events.append(self._enrich_event(mid, entry.timestamp, entry.importance, entry.metadata))
        # Already sorted by TemporalIndex, but ensure
        events.sort(key=lambda e: e.timestamp)
        return events
    
    # --------------------------------------------------------------------
    # Grouped timelines
    # --------------------------------------------------------------------
    def group_by_year(self, min_importance: float = 0.0) -> List[TimelineSegment]:
        """
        Group events by calendar year.
        """
        events = self.build_full_timeline(min_importance=min_importance)
        if not events:
            return []
        
        grouped = defaultdict(list)
        for event in events:
            year = event.datetime.year
            grouped[year].append(event)
        
        segments = []
        for year in sorted(grouped.keys()):
            year_events = grouped[year]
            start = datetime(year, 1, 1).timestamp()
            end = datetime(year, 12, 31, 23, 59, 59).timestamp()
            segments.append(TimelineSegment(
                start_time=start,
                end_time=end,
                events=year_events,
                title=f"Year {year}",
                description=f"{len(year_events)} memories"
            ))
        return segments
    
    def group_by_month(self, min_importance: float = 0.0) -> List[TimelineSegment]:
        """
        Group events by year+month.
        """
        events = self.build_full_timeline(min_importance=min_importance)
        if not events:
            return []
        
        grouped = defaultdict(list)
        for event in events:
            key = (event.datetime.year, event.datetime.month)
            grouped[key].append(event)
        
        segments = []
        for (year, month), month_events in sorted(grouped.items()):
            start = datetime(year, month, 1).timestamp()
            # End of month
            if month == 12:
                end = datetime(year+1, 1, 1).timestamp() - 1
            else:
                end = datetime(year, month+1, 1).timestamp() - 1
            segments.append(TimelineSegment(
                start_time=start,
                end_time=end,
                events=month_events,
                title=f"{year}-{month:02d}",
                description=f"{len(month_events)} memories"
            ))
        return segments
    
    def group_by_phase(self, min_importance: float = 0.0) -> List[TimelineSegment]:
        """
        Group events by life phase (as defined in TemporalIndex).
        """
        phases = LifePhase.all_phases()
        segments = []
        for phase in phases:
            memory_ids = self.temporal_index.get_memories_by_phase(phase)
            events = []
            for mid in memory_ids:
                entry = self.temporal_index._entries.get(mid)
                if entry and entry.importance >= min_importance:
                    events.append(self._enrich_event(mid, entry.timestamp, entry.importance, entry.metadata))
            if events:
                events.sort(key=lambda e: e.timestamp)
                start = events[0].timestamp
                end = events[-1].timestamp
                segments.append(TimelineSegment(
                    start_time=start,
                    end_time=end,
                    events=events,
                    title=phase.replace('_', ' ').title(),
                    description=f"{len(events)} memories from {phase}"
                ))
        return segments
    
    def group_by_custom_interval(self, interval_days: int, min_importance: float = 0.0) -> List[TimelineSegment]:
        """
        Group events into fixed‑length intervals (in days).
        """
        events = self.build_full_timeline(min_importance=min_importance)
        if not events:
            return []
        first_ts = events[0].timestamp
        last_ts = events[-1].timestamp
        interval_sec = interval_days * 86400
        segments = []
        current_start = first_ts
        while current_start <= last_ts:
            current_end = current_start + interval_sec
            segment_events = [e for e in events if current_start <= e.timestamp < current_end]
            if segment_events:
                segments.append(TimelineSegment(
                    start_time=current_start,
                    end_time=current_end,
                    events=segment_events,
                    title=f"{datetime.fromtimestamp(current_start).date()} – {datetime.fromtimestamp(current_end).date()}",
                    description=f"{len(segment_events)} memories"
                ))
            current_start = current_end
        return segments
    
    # --------------------------------------------------------------------
    # Narrative generation
    # --------------------------------------------------------------------
    def generate_narrative_summary(self, segment: TimelineSegment) -> str:
        """
        Generate a human‑readable narrative summary for a timeline segment.
        """
        lines = []
        lines.append(f"## {segment.title}")
        if segment.description:
            lines.append(segment.description)
        lines.append("")
        if not segment.events:
            lines.append("No memories in this period.")
            return "\n".join(lines)
        
        # Most important events
        important = segment.get_most_important_events(3)
        if important:
            lines.append("**Most significant memories:**")
            for event in important:
                lines.append(f"- {event.title} (importance: {event.importance:.2f})")
        lines.append("")
        
        # Chronological list
        lines.append("**Chronological events:**")
        for event in segment.events[:20]:
            dt = datetime.fromtimestamp(event.timestamp).strftime("%Y-%m-%d")
            lines.append(f"- {dt}: {event.title[:80]}")
        if len(segment.events) > 20:
            lines.append(f"- ... and {len(segment.events)-20} more events.")
        
        return "\n".join(lines)
    
    def generate_full_narrative(self, group_by: str = "year", min_importance: float = 0.0) -> str:
        """
        Generate a complete narrative of all memories, grouped by the specified method.
        """
        if group_by == "year":
            segments = self.group_by_year(min_importance)
        elif group_by == "month":
            segments = self.group_by_month(min_importance)
        elif group_by == "phase":
            segments = self.group_by_phase(min_importance)
        elif group_by == "custom":
            segments = self.group_by_custom_interval(365, min_importance)
        else:
            segments = [TimelineSegment(0, 0, self.build_full_timeline(min_importance), "All Memories")]
        
        narratives = []
        for seg in segments:
            narratives.append(self.generate_narrative_summary(seg))
        return "\n\n".join(narratives)
    
    # --------------------------------------------------------------------
    # Export formats
    # --------------------------------------------------------------------
    def export_to_json(self, group_by: str = "year", min_importance: float = 0.0) -> str:
        """Export timeline to JSON string."""
        if group_by == "year":
            segments = self.group_by_year(min_importance)
        elif group_by == "month":
            segments = self.group_by_month(min_importance)
        elif group_by == "phase":
            segments = self.group_by_phase(min_importance)
        else:
            segments = self.group_by_custom_interval(365, min_importance)
        
        data = {
            "export_time": time.time(),
            "group_by": group_by,
            "min_importance": min_importance,
            "segments": [seg.to_dict() for seg in segments]
        }
        return json.dumps(data, indent=2)
    
    def export_to_markdown(self, group_by: str = "year", min_importance: float = 0.0) -> str:
        """Export timeline as Markdown document."""
        return self.generate_full_narrative(group_by, min_importance)
    
    def export_to_html(self, group_by: str = "year", min_importance: float = 0.0) -> str:
        """Export timeline as HTML (basic styling)."""
        narrative = self.generate_full_narrative(group_by, min_importance)
        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Timeline</title>
<style>
body {{ font-family: sans-serif; margin: 2em; background: #f5f5f5; }}
.timeline {{ max-width: 800px; margin: auto; background: white; padding: 2em; border-radius: 8px; }}
h1 {{ color: #333; }}
h2 {{ border-bottom: 1px solid #ccc; padding-bottom: 0.3em; }}
.event {{ margin: 1em 0; padding: 0.5em; background: #fafafa; border-left: 4px solid #007acc; }}
.event-date {{ color: #666; font-size: 0.9em; }}
.event-title {{ font-weight: bold; }}
.event-desc {{ margin-top: 0.2em; color: #444; }}
</style>
</head>
<body>
<div class="timeline">
<h1>Timeline</h1>
{narrative.replace("## ", "<h2>").replace("\n\n", "</h2>").replace("**", "<strong>").replace("</strong>", "</strong>")}
</div>
</body>
</html>"""
        return html
    
    # --------------------------------------------------------------------
    # Milestone detection
    # --------------------------------------------------------------------
    def get_milestones(self, top_n: int = 10) -> List[TimelineEvent]:
        """Return the most important events across the entire timeline."""
        events = self.build_full_timeline()
        events.sort(key=lambda e: e.importance, reverse=True)
        return events[:top_n]
    
    def get_first_event(self) -> Optional[TimelineEvent]:
        """Return the earliest memory."""
        events = self.build_full_timeline()
        if events:
            return events[0]
        return None
    
    def get_last_event(self) -> Optional[TimelineEvent]:
        """Return the latest memory."""
        events = self.build_full_timeline()
        if events:
            return events[-1]
        return None
    
    def get_density_map(self, resolution_days: int = 30) -> Dict[str, int]:
        """
        Return a map of time intervals to memory count (density).
        Useful for heatmap visualisation.
        """
        events = self.build_full_timeline()
        if not events:
            return {}
        first_ts = events[0].timestamp
        last_ts = events[-1].timestamp
        density = {}
        current = first_ts
        while current <= last_ts:
            interval_end = current + resolution_days * 86400
            count = sum(1 for e in events if current <= e.timestamp < interval_end)
            label = datetime.fromtimestamp(current).strftime("%Y-%m-%d")
            density[label] = count
            current = interval_end
        return density
    
    # --------------------------------------------------------------------
    # Text‑based timeline visualisation (ASCII)
    # --------------------------------------------------------------------
    def render_ascii_timeline(self, width: int = 80, height: int = 20) -> str:
        """
        Render a simple ASCII timeline plot (density over time).
        """
        density = self.get_density_map(resolution_days=30)
        if not density:
            return "No data to display."
        labels = list(density.keys())
        counts = list(density.values())
        max_count = max(counts) if counts else 1
        # Scale to height
        scaled = [int((c / max_count) * (height-1)) for c in counts]
        lines = []
        for h in range(height-1, -1, -1):
            line_chars = []
            for s in scaled:
                line_chars.append('█' if s >= h else ' ')
            lines.append(''.join(line_chars))
        # Add x‑axis labels (skip most for readability)
        x_labels = []
        step = max(1, len(labels) // 10)
        for i, label in enumerate(labels):
            if i % step == 0:
                x_labels.append(label[:6])
            else:
                x_labels.append('      ')
        lines.append(''.join(x_labels))
        return "\n".join(lines)

# --------------------------------------------------------------------
# Example usage (commented)
# --------------------------------------------------------------------
"""
# Assuming temporal_index is populated
builder = TimelineBuilder(temporal_index, memory_library)

# Full events
events = builder.build_full_timeline()
print(f"Total events: {len(events)}")

# Grouped by year
years = builder.group_by_year()
for seg in years:
    print(f"{seg.title}: {len(seg.events)} events")

# Narrative
narrative = builder.generate_full_narrative(group_by="phase")
print(narrative)

# Export to JSON
json_str = builder.export_to_json("month")
with open("timeline.json", "w") as f:
    f.write(json_str)

# Milestones
top = builder.get_milestones(5)
for e in top:
    print(f"{e.title} (importance: {e.importance})")

# ASCII density chart
print(builder.render_ascii_timeline())
"""

# ====================================================================================================
# END OF timeline_builder.py (31,892 characters)
# ====================================================================================================
