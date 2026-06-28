# ====================================================================================================
# temporal_index.py – Temporal Memory Index for CrownStar‑Absolute
# Features:
#   - Chronological indexing (by timestamp, year, month, day, hour)
#   - Life phase classification (based on age or subjective time)
#   - Anniversary detection (daily, monthly, yearly reminders)
#   - Temporal cluster detection (periods with high memory density)
#   - Range queries, nearest neighbour queries
# ====================================================================================================

import time
import bisect
from typing import List, Dict, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("CrownStar.TemporalIndex")

# --------------------------------------------------------------------
# Life Phase Definitions
# --------------------------------------------------------------------
class LifePhase:
    """Enumeration of life phases (can be customised by age or eternal existence)."""
    INFANCY = "infancy"
    EARLY_CHILDHOOD = "early_childhood"
    MIDDLE_CHILDHOOD = "middle_childhood"
    ADOLESCENCE = "adolescence"
    EARLY_ADULTHOOD = "early_adulthood"
    ADULTHOOD = "adulthood"
    MIDDLE_ADULTHOOD = "middle_adulthood"
    LATE_ADULTHOOD = "late_adulthood"
    ELDER = "elder"
    ETERNAL = "eternal"
    
    @staticmethod
    def from_age(age_years: int) -> str:
        """Map age in years to a life phase."""
        if age_years < 2:
            return LifePhase.INFANCY
        elif age_years < 6:
            return LifePhase.EARLY_CHILDHOOD
        elif age_years < 11:
            return LifePhase.MIDDLE_CHILDHOOD
        elif age_years < 18:
            return LifePhase.ADOLESCENCE
        elif age_years < 25:
            return LifePhase.EARLY_ADULTHOOD
        elif age_years < 45:
            return LifePhase.ADULTHOOD
        elif age_years < 60:
            return LifePhase.MIDDLE_ADULTHOOD
        elif age_years < 75:
            return LifePhase.LATE_ADULTHOOD
        elif age_years < 100:
            return LifePhase.ELDER
        else:
            return LifePhase.ETERNAL
    
    @staticmethod
    def all_phases() -> List[str]:
        return [
            LifePhase.INFANCY, LifePhase.EARLY_CHILDHOOD, LifePhase.MIDDLE_CHILDHOOD,
            LifePhase.ADOLESCENCE, LifePhase.EARLY_ADULTHOOD, LifePhase.ADULTHOOD,
            LifePhase.MIDDLE_ADULTHOOD, LifePhase.LATE_ADULTHOOD,
            LifePhase.ELDER, LifePhase.ETERNAL
        ]

# --------------------------------------------------------------------
# Temporal Index Entry
# --------------------------------------------------------------------
@dataclass
class TemporalEntry:
    """A single entry in the temporal index."""
    memory_id: str
    timestamp: float
    phase: str = ""
    year: int = 0
    month: int = 0
    day: int = 0
    hour: int = 0
    importance: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)

# --------------------------------------------------------------------
# Temporal Cluster
# --------------------------------------------------------------------
@dataclass
class TemporalCluster:
    """A period of time with high memory density."""
    start_time: float
    end_time: float
    memory_ids: List[str]
    density: float  # memories per day
    theme: str = ""

# --------------------------------------------------------------------
# Main Temporal Index
# --------------------------------------------------------------------
class TemporalIndex:
    """
    Indexes memories by time, supports chronological queries, life phase grouping,
    anniversary detection, and temporal clustering.
    """
    
    def __init__(self, reference_birth_time: Optional[float] = None):
        """
        Args:
            reference_birth_time: timestamp of the person's birth (for life phase mapping).
                                 If None, phase will be based on absolute time (years since 1970).
        """
        self.reference_birth_time = reference_birth_time
        self._entries: Dict[str, TemporalEntry] = {}          # memory_id -> entry
        self._by_timestamp: List[Tuple[float, str]] = []      # sorted list of (timestamp, memory_id)
        self._by_year: Dict[int, List[str]] = defaultdict(list)
        self._by_month: Dict[Tuple[int, int], List[str]] = defaultdict(list)  # (year, month)
        self._by_day: Dict[str, List[str]] = defaultdict(list)                # YYYY-MM-DD
        self._by_phase: Dict[str, List[str]] = defaultdict(list)
        self._needs_sort = False
        logger.info("TemporalIndex initialised")
    
    # --------------------------------------------------------------------
    # Add / Remove
    # --------------------------------------------------------------------
    def add_memory(self, memory_id: str, timestamp: float, importance: float = 0.5,
                   metadata: Optional[Dict] = None, phase_override: Optional[str] = None):
        """
        Add a memory to the temporal index.
        """
        if memory_id in self._entries:
            self.remove_memory(memory_id)
        
        dt = datetime.fromtimestamp(timestamp)
        year = dt.year
        month = dt.month
        day = dt.day
        hour = dt.hour
        
        # Determine life phase
        if phase_override:
            phase = phase_override
        elif self.reference_birth_time is not None:
            age_years = (timestamp - self.reference_birth_time) / (365.25 * 86400)
            phase = LifePhase.from_age(age_years)
        else:
            # Fallback: phase based on year of life (simplified)
            age_years = year - 1970  # arbitrary baseline
            phase = LifePhase.from_age(age_years)
        
        entry = TemporalEntry(
            memory_id=memory_id,
            timestamp=timestamp,
            phase=phase,
            year=year,
            month=month,
            day=day,
            hour=hour,
            importance=importance,
            metadata=metadata or {}
        )
        self._entries[memory_id] = entry
        self._by_timestamp.append((timestamp, memory_id))
        self._by_year[year].append(memory_id)
        self._by_month[(year, month)].append(memory_id)
        day_key = f"{year:04d}-{month:02d}-{day:02d}"
        self._by_day[day_key].append(memory_id)
        self._by_phase[phase].append(memory_id)
        self._needs_sort = True
        
        logger.debug(f"Added memory {memory_id} to temporal index at {timestamp}")
    
    def remove_memory(self, memory_id: str):
        """Remove a memory from the temporal index."""
        if memory_id not in self._entries:
            return
        entry = self._entries[memory_id]
        # Remove from lists (inefficient but acceptable for moderate sizes)
        self._by_timestamp = [(ts, mid) for ts, mid in self._by_timestamp if mid != memory_id]
        self._by_year[entry.year] = [mid for mid in self._by_year[entry.year] if mid != memory_id]
        self._by_month[(entry.year, entry.month)] = [mid for mid in self._by_month[(entry.year, entry.month)] if mid != memory_id]
        day_key = f"{entry.year:04d}-{entry.month:02d}-{entry.day:02d}"
        self._by_day[day_key] = [mid for mid in self._by_day[day_key] if mid != memory_id]
        self._by_phase[entry.phase] = [mid for mid in self._by_phase[entry.phase] if mid != memory_id]
        del self._entries[memory_id]
        self._needs_sort = True
        logger.debug(f"Removed memory {memory_id} from temporal index")
    
    def _ensure_sorted(self):
        """Ensure the timestamp list is sorted (call before binary searches)."""
        if self._needs_sort:
            self._by_timestamp.sort(key=lambda x: x[0])
            self._needs_sort = False
    
    # --------------------------------------------------------------------
    # Range Queries
    # --------------------------------------------------------------------
    def get_memories_in_range(self, start_time: float, end_time: float) -> List[str]:
        """Return memory IDs with timestamps in [start_time, end_time]."""
        self._ensure_sorted()
        # Binary search for start and end indices
        timestamps = [t for t, _ in self._by_timestamp]
        left = bisect.bisect_left(timestamps, start_time)
        right = bisect.bisect_right(timestamps, end_time)
        return [mid for _, mid in self._by_timestamp[left:right]]
    
    def get_memories_before(self, timestamp: float, limit: int = 100) -> List[str]:
        """Return memory IDs with timestamp < given time, newest first (up to limit)."""
        self._ensure_sorted()
        timestamps = [t for t, _ in self._by_timestamp]
        idx = bisect.bisect_left(timestamps, timestamp)
        # Get up to limit oldest? Actually we want newest before timestamp, so reverse slice.
        slice_ = self._by_timestamp[:idx]
        slice_.reverse()
        return [mid for _, mid in slice_[:limit]]
    
    def get_memories_after(self, timestamp: float, limit: int = 100) -> List[str]:
        """Return memory IDs with timestamp > given time, oldest first (up to limit)."""
        self._ensure_sorted()
        timestamps = [t for t, _ in self._by_timestamp]
        idx = bisect.bisect_right(timestamps, timestamp)
        return [mid for _, mid in self._by_timestamp[idx:idx+limit]]
    
    def get_memories_by_year(self, year: int) -> List[str]:
        """Return memory IDs from a specific year."""
        return self._by_year.get(year, [])
    
    def get_memories_by_month(self, year: int, month: int) -> List[str]:
        """Return memory IDs from a specific month."""
        return self._by_month.get((year, month), [])
    
    def get_memories_by_day(self, year: int, month: int, day: int) -> List[str]:
        """Return memory IDs from a specific calendar day."""
        day_key = f"{year:04d}-{month:02d}-{day:02d}"
        return self._by_day.get(day_key, [])
    
    def get_memories_by_phase(self, phase: str) -> List[str]:
        """Return memory IDs from a specific life phase."""
        return self._by_phase.get(phase, [])
    
    # --------------------------------------------------------------------
    # Anniversary Detection
    # --------------------------------------------------------------------
    def get_anniversaries_today(self, reference_date: Optional[float] = None) -> List[Dict]:
        """
        Return memories that occurred on the same month/day as today (or reference date).
        Each result includes memory_id, original date, years ago.
        """
        now = reference_date if reference_date is not None else time.time()
        dt_now = datetime.fromtimestamp(now)
        results = []
        for entry in self._entries.values():
            dt_orig = datetime.fromtimestamp(entry.timestamp)
            if dt_orig.month == dt_now.month and dt_orig.day == dt_now.day:
                years_ago = dt_now.year - dt_orig.year
                results.append({
                    "memory_id": entry.memory_id,
                    "original_timestamp": entry.timestamp,
                    "years_ago": years_ago,
                    "phase_at_that_time": entry.phase
                })
        return results
    
    def get_upcoming_anniversaries(self, days_ahead: int = 7) -> List[Dict]:
        """
        Return memories with anniversaries in the next days_ahead days.
        """
        now = datetime.now()
        results = []
        for entry in self._entries.values():
            dt_orig = datetime.fromtimestamp(entry.timestamp)
            # Create a date for this year's anniversary
            this_year_anniv = datetime(now.year, dt_orig.month, dt_orig.day)
            if this_year_anniv < now:
                next_year_anniv = datetime(now.year + 1, dt_orig.month, dt_orig.day)
                days_until = (next_year_anniv - now).days
                if 0 <= days_until <= days_ahead:
                    results.append({
                        "memory_id": entry.memory_id,
                        "anniversary_date": next_year_anniv.timestamp(),
                        "days_until": days_until,
                        "years_ago": now.year - dt_orig.year + 1
                    })
            else:
                days_until = (this_year_anniv - now).days
                if days_until <= days_ahead:
                    results.append({
                        "memory_id": entry.memory_id,
                        "anniversary_date": this_year_anniv.timestamp(),
                        "days_until": days_until,
                        "years_ago": now.year - dt_orig.year
                    })
        results.sort(key=lambda x: x["days_until"])
        return results
    
    # --------------------------------------------------------------------
    # Temporal Clusters (High Density Periods)
    # --------------------------------------------------------------------
    def find_clusters(self, window_days: int = 7, min_memories: int = 5) -> List[TemporalCluster]:
        """
        Detect periods where memory density exceeds threshold.
        Uses sliding window over the sorted timeline.
        """
        self._ensure_sorted()
        if not self._by_timestamp:
            return []
        
        timestamps = [t for t, _ in self._by_timestamp]
        clusters = []
        window_seconds = window_days * 86400
        i = 0
        while i < len(timestamps):
            start = timestamps[i]
            # Find window end
            j = i
            while j < len(timestamps) and timestamps[j] - start <= window_seconds:
                j += 1
            count = j - i
            density = count / window_days
            if count >= min_memories:
                memory_ids = [mid for _, mid in self._by_timestamp[i:j]]
                clusters.append(TemporalCluster(
                    start_time=start,
                    end_time=timestamps[j-1] if j > i else start,
                    memory_ids=memory_ids,
                    density=density
                ))
                i = j
            else:
                i += 1
        # Merge overlapping clusters (optional)
        merged = []
        for cluster in clusters:
            if merged and cluster.start_time <= merged[-1].end_time + window_seconds:
                merged[-1].end_time = max(merged[-1].end_time, cluster.end_time)
                merged[-1].memory_ids.extend(cluster.memory_ids)
                merged[-1].density = (merged[-1].density + cluster.density) / 2
            else:
                merged.append(cluster)
        return merged
    
    # --------------------------------------------------------------------
    # Chronological Timeline (ordered list)
    # --------------------------------------------------------------------
    def get_timeline(self, reverse: bool = False, limit: Optional[int] = None) -> List[Tuple[float, str]]:
        """Return the entire timeline as (timestamp, memory_id) pairs."""
        self._ensure_sorted()
        timeline = self._by_timestamp.copy()
        if reverse:
            timeline.reverse()
        if limit:
            timeline = timeline[:limit]
        return timeline
    
    # --------------------------------------------------------------------
    # Statistics
    # --------------------------------------------------------------------
    def get_statistics(self) -> Dict:
        """Return statistics about the temporal index."""
        self._ensure_sorted()
        if not self._by_timestamp:
            return {"total_memories": 0}
        first_ts = self._by_timestamp[0][0]
        last_ts = self._by_timestamp[-1][0]
        time_span_days = (last_ts - first_ts) / 86400
        return {
            "total_memories": len(self._entries),
            "first_memory_time": first_ts,
            "last_memory_time": last_ts,
            "time_span_days": time_span_days,
            "years_covered": len(self._by_year),
            "phases_covered": list(self._by_phase.keys()),
            "memories_by_phase": {phase: len(ids) for phase, ids in self._by_phase.items()}
        }
    
    # --------------------------------------------------------------------
    # Serialisation (to/from dict)
    # --------------------------------------------------------------------
    def to_dict(self) -> Dict:
        """Convert the temporal index to a dictionary for serialisation."""
        entries_dict = {}
        for mid, entry in self._entries.items():
            entries_dict[mid] = {
                "memory_id": entry.memory_id,
                "timestamp": entry.timestamp,
                "phase": entry.phase,
                "year": entry.year,
                "month": entry.month,
                "day": entry.day,
                "hour": entry.hour,
                "importance": entry.importance,
                "metadata": entry.metadata
            }
        return {
            "reference_birth_time": self.reference_birth_time,
            "entries": entries_dict
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TemporalIndex':
        idx = cls(reference_birth_time=data.get("reference_birth_time"))
        for mid, entry_data in data.get("entries", {}).items():
            idx.add_memory(
                memory_id=entry_data["memory_id"],
                timestamp=entry_data["timestamp"],
                importance=entry_data.get("importance", 0.5),
                metadata=entry_data.get("metadata", {}),
                phase_override=entry_data.get("phase")
            )
        return idx
    
    def clear(self):
        """Clear all entries from the index."""
        self._entries.clear()
        self._by_timestamp.clear()
        self._by_year.clear()
        self._by_month.clear()
        self._by_day.clear()
        self._by_phase.clear()
        self._needs_sort = False
        logger.info("TemporalIndex cleared")

# --------------------------------------------------------------------
# Convenience function: integrate with MemoryLibrary
# --------------------------------------------------------------------
def index_memory_library(library, temporal_index: TemporalIndex):
    """Populate a temporal index from all books in a MemoryLibrary."""
    for section in library.sections.values():
        for shelf in section.shelves.values():
            for book in shelf.books:
                if book.publication_date:
                    temporal_index.add_memory(
                        memory_id=book.book_id,
                        timestamp=book.publication_date,
                        importance=book.importance,
                        metadata={"title": book.title, "author": book.author}
                    )

# --------------------------------------------------------------------
# Example usage (commented)
# --------------------------------------------------------------------
"""
# Create temporal index
tidx = TemporalIndex(reference_birth_time=datetime(1990, 1, 1).timestamp())

# Add some memories
tidx.add_memory("mem1", datetime(2020, 1, 15).timestamp(), importance=0.8)
tidx.add_memory("mem2", datetime(2021, 6, 20).timestamp())
tidx.add_memory("mem3", datetime(2022, 12, 25).timestamp(), importance=0.9)

# Range query
memories = tidx.get_memories_in_range(datetime(2021, 1, 1).timestamp(), datetime(2023, 1, 1).timestamp())
print(f"Memories in 2021-2022: {memories}")

# Anniversaries today
ann = tidx.get_anniversaries_today()
print(f"Anniversaries today: {ann}")

# Upcoming anniversaries
upcoming = tidx.get_upcoming_anniversaries(days_ahead=30)
print(f"Upcoming anniversaries: {len(upcoming)}")

# Clusters
clusters = tidx.find_clusters(window_days=30, min_memories=2)
for c in clusters:
    print(f"Cluster from {datetime.fromtimestamp(c.start_time)} to {datetime.fromtimestamp(c.end_time)}, density={c.density:.2f} mem/day")

# Statistics
print(tidx.get_statistics())
"""

# ====================================================================================================
# END OF temporal_index.py (32,784 characters)
# ====================================================================================================
