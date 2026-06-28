# ====================================================================================================
# experiential.py – Experiential Memory for CrownStar‑Absolute
# Implements:
#   - Literal recall: full, exact reconstruction
#   - Sketchy recall: impressionistic, vague, with configurable clarity
#   - Reliving: full sensory reconstruction (simulated)
#   - Multimodal fields: visual, audio, emotion, tactile, olfactory, gustatory
# ====================================================================================================

import time
import uuid
import random
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger("CrownStar.Experiential")

# --------------------------------------------------------------------
# Multimodal field dataclasses
# --------------------------------------------------------------------
@dataclass
class VisualMemory:
    """Visual component of an experiential memory."""
    description: str
    lighting: str = "natural"
    colors: List[str] = field(default_factory=list)
    objects: List[str] = field(default_factory=list)
    scene_type: str = "sunlit"  # sunlit, interior, vehicle, exterior
    clarity: float = 1.0
    
    def to_dict(self) -> Dict:
        return {
            "description": self.description,
            "lighting": self.lighting,
            "colors": self.colors,
            "objects": self.objects,
            "scene_type": self.scene_type,
            "clarity": self.clarity
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'VisualMemory':
        return cls(
            description=data.get("description", ""),
            lighting=data.get("lighting", "natural"),
            colors=data.get("colors", []),
            objects=data.get("objects", []),
            scene_type=data.get("scene_type", "sunlit"),
            clarity=data.get("clarity", 1.0)
        )

@dataclass
class AudioMemory:
    """Audio component of an experiential memory."""
    sound: str
    volume: float = 0.5
    pitch: float = 440.0
    duration: float = 1.0
    clarity: float = 1.0
    
    def to_dict(self) -> Dict:
        return {
            "sound": self.sound,
            "volume": self.volume,
            "pitch": self.pitch,
            "duration": self.duration,
            "clarity": self.clarity
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AudioMemory':
        return cls(
            sound=data.get("sound", ""),
            volume=data.get("volume", 0.5),
            pitch=data.get("pitch", 440.0),
            duration=data.get("duration", 1.0),
            clarity=data.get("clarity", 1.0)
        )

@dataclass
class EmotionalMemory:
    """Emotional tone of an experiential memory."""
    primary_emotion: str = "neutral"
    valence: float = 0.5   # -1 to 1 (negative to positive)
    arousal: float = 0.5   # 0 to 1 (calm to excited)
    intensity: float = 0.5
    
    def to_dict(self) -> Dict:
        return {
            "primary_emotion": self.primary_emotion,
            "valence": self.valence,
            "arousal": self.arousal,
            "intensity": self.intensity
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'EmotionalMemory':
        return cls(
            primary_emotion=data.get("primary_emotion", "neutral"),
            valence=data.get("valence", 0.5),
            arousal=data.get("arousal", 0.5),
            intensity=data.get("intensity", 0.5)
        )

@dataclass
class TactileMemory:
    """Tactile (touch) component."""
    texture: str = ""
    temperature: float = 25.0
    pressure: float = 0.0
    pleasantness: float = 0.5
    
    def to_dict(self) -> Dict:
        return {
            "texture": self.texture,
            "temperature": self.temperature,
            "pressure": self.pressure,
            "pleasantness": self.pleasantness
        }

@dataclass
class OlfactoryMemory:
    """Smell component."""
    scent: str = ""
    intensity: float = 0.5
    pleasantness: float = 0.5

@dataclass
class GustatoryMemory:
    """Taste component."""
    flavor: str = ""
    sweetness: float = 0.0
    saltiness: float = 0.0
    sourness: float = 0.0
    bitterness: float = 0.0
    umami: float = 0.0

# --------------------------------------------------------------------
# Experiential Memory Main Class
# --------------------------------------------------------------------
class ExperientialMemory:
    """
    A complete experiential memory with multiple sensory modalities.
    Supports:
      - literal_recall(): exact, detailed reconstruction
      - sketchy_recall(clarity): vague, impressionistic recall
      - relive(): full sensory reconstruction (simulated)
    """
    
    def __init__(self, 
                 memory_id: Optional[str] = None,
                 title: str = "",
                 narrative: str = "",
                 timestamp: Optional[float] = None,
                 importance: float = 0.5,
                 visual: Optional[VisualMemory] = None,
                 audio: Optional[AudioMemory] = None,
                 emotion: Optional[EmotionalMemory] = None,
                 tactile: Optional[TactileMemory] = None,
                 olfactory: Optional[OlfactoryMemory] = None,
                 gustatory: Optional[GustatoryMemory] = None,
                 location: str = "",
                 tags: List[str] = None):
        
        self.memory_id = memory_id or str(uuid.uuid4())
        self.title = title
        self.narrative = narrative
        self.timestamp = timestamp or time.time()
        self.importance = importance
        self.visual = visual or VisualMemory(description="")
        self.audio = audio or AudioMemory(sound="")
        self.emotion = emotion or EmotionalMemory()
        self.tactile = tactile
        self.olfactory = olfactory
        self.gustatory = gustatory
        self.location = location
        self.tags = tags or []
        self._recall_count = 0
        self._last_recall_time = 0.0
    
    # --------------------------------------------------------------------
    # Recall methods
    # --------------------------------------------------------------------
    def literal_recall(self) -> Dict[str, Any]:
        """
        Literal recall: exact, detailed reconstruction of the experience.
        Returns a dictionary with all available fields.
        """
        self._recall_count += 1
        self._last_recall_time = time.time()
        
        result = {
            "memory_id": self.memory_id,
            "title": self.title,
            "narrative": self.narrative,
            "timestamp": self.timestamp,
            "importance": self.importance,
            "location": self.location,
            "tags": self.tags,
            "visual": self.visual.to_dict() if self.visual else None,
            "audio": self.audio.to_dict() if self.audio else None,
            "emotion": self.emotion.to_dict() if self.emotion else None,
            "tactile": self.tactile.to_dict() if self.tactile else None,
            "olfactory": self.olfactory.__dict__ if self.olfactory else None,
            "gustatory": self.gustatory.__dict__ if self.gustatory else None,
            "recall_type": "literal",
            "recall_fidelity": 1.0
        }
        return result
    
    def sketchy_recall(self, clarity: float = 0.4) -> Dict[str, Any]:
        """
        Sketchy recall: vague, impressionistic, with missing details.
        Lower clarity → more missing elements, less detail.
        """
        self._recall_count += 1
        self._last_recall_time = time.time()
        clarity = max(0.0, min(1.0, clarity))
        
        # Obfuscate narrative (truncate, random omissions)
        narrative_words = self.narrative.split()
        kept_count = max(1, int(len(narrative_words) * clarity))
        kept = narrative_words[:kept_count]
        if kept_count < len(narrative_words):
            kept.append("... [vague memory] ...")
        sketchy_narrative = " ".join(kept)
        
        # Visual sketchy
        visual_sketch = None
        if self.visual and self.visual.description:
            if clarity > 0.5:
                visual_sketch = f"I vaguely recall {self.visual.description[:100]}..."
            else:
                visual_sketch = "There was something visual... I can't quite remember."
        
        # Emotion sketchy
        emotion_sketch = None
        if self.emotion and self.emotion.primary_emotion != "neutral":
            if clarity > 0.6:
                emotion_sketch = f"I felt {self.emotion.primary_emotion}, I think."
            else:
                emotion_sketch = "There was some emotion, but it's hazy."
        
        # Missing elements list
        missing = []
        if clarity < 0.3:
            missing.append("most details")
        if clarity < 0.5:
            missing.append("specific words")
        if clarity < 0.7 and self.visual:
            missing.append("visual specifics")
        if clarity < 0.6 and self.audio and self.audio.sound:
            missing.append("sounds")
        
        result = {
            "memory_id": self.memory_id,
            "title": self.title if clarity > 0.5 else "[unclear title]",
            "narrative": sketchy_narrative,
            "timestamp_approx": self._format_timestamp_vague(),
            "visual": visual_sketch,
            "emotion": emotion_sketch,
            "missing_elements": missing,
            "clarity": clarity,
            "recall_type": "sketchy",
            "recall_fidelity": clarity * 0.8
        }
        return result
    
    def relive(self, intensity: float = 1.0) -> Dict[str, Any]:
        """
        Full reliving: simulate the experience with high immersion.
        intensity (0‑1) controls how vividly it's reconstructed.
        """
        self._recall_count += 1
        self._last_recall_time = time.time()
        
        # Build a rich reconstruction
        reconstruction = {
            "memory_id": self.memory_id,
            "title": self.title,
            "full_narrative": self.narrative,
            "timestamp": self.timestamp,
            "location": self.location,
            "recall_type": "reliving",
            "immersion": intensity,
            "reconstructed_visual": None,
            "reconstructed_audio": None,
            "reconstructed_emotion": None,
            "tactile_simulation": None,
            "olfactory_simulation": None,
            "gustatory_simulation": None
        }
        
        # Visual reliving
        if self.visual and self.visual.description:
            reconstruction["reconstructed_visual"] = {
                "description": self.visual.description,
                "lighting": self.visual.lighting,
                "colors": self.visual.colors,
                "objects": self.visual.objects,
                "vividness": intensity * self.visual.clarity
            }
        
        # Audio reliving
        if self.audio and self.audio.sound:
            reconstruction["reconstructed_audio"] = {
                "sound": self.audio.sound,
                "volume": self.audio.volume * intensity,
                "pitch": self.audio.pitch,
                "clarity": intensity * self.audio.clarity
            }
        
        # Emotion reliving
        if self.emotion:
            reconstruction["reconstructed_emotion"] = {
                "primary": self.emotion.primary_emotion,
                "valence": self.emotion.valence,
                "arousal": self.emotion.arousal * intensity,
                "intensity": self.emotion.intensity * intensity
            }
        
        # Tactile simulation
        if self.tactile:
            reconstruction["tactile_simulation"] = {
                "texture": self.tactile.texture,
                "temperature": self.tactile.temperature,
                "pressure": self.tactile.pressure * intensity,
                "pleasantness": self.tactile.pleasantness
            }
        
        # Olfactory simulation
        if self.olfactory:
            reconstruction["olfactory_simulation"] = {
                "scent": self.olfactory.scent,
                "intensity": self.olfactory.intensity * intensity
            }
        
        # Gustatory simulation
        if self.gustatory:
            reconstruction["gustatory_simulation"] = {
                "flavor": self.gustatory.flavor,
                "sweetness": self.gustatory.sweetness * intensity,
                "saltiness": self.gustatory.saltiness * intensity,
                "sourness": self.gustatory.sourness * intensity,
                "bitterness": self.gustatory.bitterness * intensity,
                "umami": self.gustatory.umami * intensity
            }
        
        return reconstruction
    
    def _format_timestamp_vague(self) -> str:
        """Return a vague description of the timestamp."""
        dt = datetime.fromtimestamp(self.timestamp)
        now = datetime.now()
        years_diff = now.year - dt.year
        if years_diff > 5:
            return f"around {dt.year}"
        elif years_diff > 1:
            return f"about {years_diff} years ago"
        else:
            months_diff = (now - dt).days // 30
            if months_diff > 1:
                return f"about {months_diff} months ago"
            else:
                return "recently"
    
    # --------------------------------------------------------------------
    # Serialisation (to/from dict)
    # --------------------------------------------------------------------
    def to_dict(self) -> Dict:
        """Convert experiential memory to a dictionary for JSON/XML serialisation."""
        return {
            "id": self.memory_id,
            "title": self.title,
            "narrative": self.narrative,
            "timestamp": self.timestamp,
            "importance": self.importance,
            "location": self.location,
            "tags": self.tags,
            "visual": self.visual.to_dict() if self.visual else None,
            "audio": self.audio.to_dict() if self.audio else None,
            "emotion": self.emotion.to_dict() if self.emotion else None,
            "tactile": self.tactile.to_dict() if self.tactile else None,
            "olfactory": self.olfactory.__dict__ if self.olfactory else None,
            "gustatory": self.gustatory.__dict__ if self.gustatory else None,
            "recall_count": self._recall_count,
            "last_recall": self._last_recall_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ExperientialMemory':
        """Reconstruct an experiential memory from a dictionary."""
        visual = None
        if data.get("visual"):
            visual = VisualMemory.from_dict(data["visual"])
        audio = None
        if data.get("audio"):
            audio = AudioMemory.from_dict(data["audio"])
        emotion = None
        if data.get("emotion"):
            emotion = EmotionalMemory.from_dict(data["emotion"])
        tactile = None
        if data.get("tactile"):
            tactile = TactileMemory(**data["tactile"])
        olfactory = None
        if data.get("olfactory"):
            olfactory = OlfactoryMemory(**data["olfactory"])
        gustatory = None
        if data.get("gustatory"):
            gustatory = GustatoryMemory(**data["gustatory"])
        
        mem = cls(
            memory_id=data.get("id"),
            title=data.get("title", ""),
            narrative=data.get("narrative", ""),
            timestamp=data.get("timestamp"),
            importance=data.get("importance", 0.5),
            visual=visual,
            audio=audio,
            emotion=emotion,
            tactile=tactile,
            olfactory=olfactory,
            gustatory=gustatory,
            location=data.get("location", ""),
            tags=data.get("tags", [])
        )
        mem._recall_count = data.get("recall_count", 0)
        mem._last_recall_time = data.get("last_recall", 0.0)
        return mem
    
    # --------------------------------------------------------------------
    # Create from current perception (factory method)
    # --------------------------------------------------------------------
    @classmethod
    def from_perception(cls, title: str, narrative: str, 
                        visual_desc: Optional[str] = None,
                        emotion: Optional[str] = None,
                        location: Optional[str] = None,
                        tags: Optional[List[str]] = None) -> 'ExperientialMemory':
        """Create a new experiential memory from current perception (simulated)."""
        visual = VisualMemory(description=visual_desc or "") if visual_desc else None
        emot = EmotionalMemory(primary_emotion=emotion or "neutral") if emotion else None
        return cls(
            title=title,
            narrative=narrative,
            visual=visual,
            emotion=emot,
            location=location or "",
            tags=tags or []
        )
    
    # --------------------------------------------------------------------
    # Statistics
    # --------------------------------------------------------------------
    def get_stats(self) -> Dict:
        """Return recall statistics for this memory."""
        return {
            "memory_id": self.memory_id,
            "recall_count": self._recall_count,
            "last_recall": self._last_recall_time,
            "importance": self.importance,
            "has_visual": self.visual is not None and bool(self.visual.description),
            "has_audio": self.audio is not None and bool(self.audio.sound),
            "has_emotion": self.emotion is not None,
            "has_tactile": self.tactile is not None,
            "has_olfactory": self.olfactory is not None,
            "has_gustatory": self.gustatory is not None
        }
    
    def update_importance(self, delta: float):
        """Adjust importance based on recall frequency or external events."""
        self.importance = max(0.0, min(1.0, self.importance + delta))
    
    # --------------------------------------------------------------------
    # XPointer integration (return pointer to this memory)
    # --------------------------------------------------------------------
    def xpointer(self) -> str:
        """Return an XPointer that points to this memory (if ID is valid)."""
        return f'xpointer(id("{self.memory_id}"))'


# --------------------------------------------------------------------
# Example usage (commented)
# --------------------------------------------------------------------
"""
# Create an experiential memory
mem = ExperientialMemory(
    title="A beautiful sunset",
    narrative="I watched the sun set over the ocean, colours of orange and pink.",
    location="Beach",
    tags=["nature", "peaceful"],
    visual=VisualMemory(description="Orange sky reflecting on water", lighting="golden hour", colors=["orange", "pink"]),
    emotion=EmotionalMemory(primary_emotion="joy", valence=0.9, arousal=0.4, intensity=0.7)
)

# Literal recall
print(mem.literal_recall())

# Sketchy recall (low clarity)
print(mem.sketchy_recall(clarity=0.3))

# Relive
print(mem.relive(intensity=0.9))

# Serialise
d = mem.to_dict()
mem2 = ExperientialMemory.from_dict(d)
"""

# ====================================================================================================
# END OF experiential.py (31,892 characters)
# ====================================================================================================
