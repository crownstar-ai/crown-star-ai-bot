# ====================================================================================================
# multimodal_sensory.py – Auditory, Olfactory, Gustatory Memory for CrownStar‑Absolute
# Implements:
#   - AudioMemory: sounds, speech, music, environmental audio
#   - OlfactoryMemory: scents, intensity, pleasantness, emotional triggers
#   - GustatoryMemory: tastes (sweet, sour, salty, bitter, umami), enjoyment
# ====================================================================================================

import random
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
import time

# --------------------------------------------------------------------
# 1. AudioMemory
# --------------------------------------------------------------------
@dataclass
class AudioMemory:
    """
    Memory of a sound: can be speech, music, environmental noise, or silence.
    """
    sound_type: str = "environmental"  # speech, music, environmental, alert, silence
    description: str = ""
    volume: float = 0.5          # 0.0 (silent) to 1.0 (loud)
    pitch: float = 440.0         # Hz
    duration_seconds: float = 1.0
    clarity: float = 1.0         # 0.0 (muffled) to 1.0 (crystal clear)
    
    # Speech specific
    is_speech: bool = False
    transcription: str = ""
    speaker: str = ""
    language: str = "en"
    emotional_tone: str = "neutral"  # happy, sad, angry, fearful, neutral
    speech_rate: float = 120.0       # words per minute
    
    # Music specific
    is_music: bool = False
    genre: str = ""
    artist: str = ""
    song_title: str = ""
    tempo_bpm: float = 120.0
    key: str = "C major"
    
    # Environmental specific
    source: str = ""             # e.g., "traffic", "rain", "birds", "wind"
    is_continuous: bool = True
    is_looping: bool = False
    
    def render(self) -> str:
        """Generate a textual description of the audio memory."""
        parts = []
        if self.sound_type == "silence":
            parts.append("I remember complete silence.")
            return " ".join(parts)
        
        parts.append(f"I remember hearing {self.description if self.description else 'a sound'}.")
        # Volume
        vol_desc = "loud" if self.volume > 0.7 else "moderate" if self.volume > 0.3 else "quiet"
        parts.append(f"It was {vol_desc} (volume {self.volume:.2f}) with a pitch around {self.pitch:.0f} Hz.")
        # Clarity
        if self.clarity < 0.3:
            parts.append("The sound was muffled and unclear.")
        elif self.clarity < 0.7:
            parts.append("The sound was somewhat clear.")
        else:
            parts.append("The sound was crystal clear.")
        # Duration
        if self.duration_seconds > 0:
            parts.append(f"It lasted about {self.duration_seconds:.1f} seconds.")
        
        # Speech
        if self.is_speech and self.transcription:
            parts.append(f"{self.speaker or 'Someone'} said: \"{self.transcription}\"")
            if self.emotional_tone != "neutral":
                parts.append(f"Their voice sounded {self.emotional_tone}.")
            if self.speech_rate > 0:
                rate_desc = "fast" if self.speech_rate > 150 else "slow" if self.speech_rate < 80 else "normal"
                parts.append(f"They spoke at a {rate_desc} pace.")
        
        # Music
        if self.is_music and self.song_title:
            parts.append(f"The music was \"{self.song_title}\" by {self.artist or 'unknown'}.")
            if self.genre:
                parts.append(f"It was a {self.genre} piece.")
            if self.tempo_bpm > 0:
                tempo_desc = "upbeat" if self.tempo_bpm > 120 else "moderate" if self.tempo_bpm > 80 else "slow"
                parts.append(f"The tempo was {tempo_desc} ({self.tempo_bpm:.0f} BPM).")
        
        # Environmental
        if self.sound_type == "environmental" and self.source:
            parts.append(f"The sound came from {self.source}.")
            if self.is_continuous:
                parts.append("It was continuous.")
            else:
                parts.append("It was intermittent.")
        
        return " ".join(parts)
    
    def to_dict(self) -> Dict:
        return {
            "type": "audio",
            "sound_type": self.sound_type,
            "description": self.description,
            "volume": self.volume,
            "pitch": self.pitch,
            "duration_seconds": self.duration_seconds,
            "clarity": self.clarity,
            "is_speech": self.is_speech,
            "transcription": self.transcription,
            "speaker": self.speaker,
            "language": self.language,
            "emotional_tone": self.emotional_tone,
            "speech_rate": self.speech_rate,
            "is_music": self.is_music,
            "genre": self.genre,
            "artist": self.artist,
            "song_title": self.song_title,
            "tempo_bpm": self.tempo_bpm,
            "key": self.key,
            "source": self.source,
            "is_continuous": self.is_continuous,
            "is_looping": self.is_looping
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AudioMemory':
        # Filter only keys that exist in dataclass
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)
    
    @classmethod
    def from_speech(cls, text: str, speaker: str = "", emotion: str = "neutral") -> 'AudioMemory':
        """Factory: create a speech audio memory."""
        return cls(
            sound_type="speech",
            description=f"Speech from {speaker or 'someone'}",
            is_speech=True,
            transcription=text,
            speaker=speaker,
            emotional_tone=emotion,
            volume=0.6,
            clarity=0.9,
            duration_seconds=len(text) * 0.1
        )
    
    @classmethod
    def from_music(cls, title: str, artist: str = "", genre: str = "") -> 'AudioMemory':
        """Factory: create a music audio memory."""
        return cls(
            sound_type="music",
            description=f"Music: {title}",
            is_music=True,
            song_title=title,
            artist=artist,
            genre=genre,
            volume=0.5,
            clarity=0.8,
            tempo_bpm=120.0
        )
    
    @classmethod
    def from_environmental(cls, source: str, continuous: bool = True) -> 'AudioMemory':
        """Factory: create an environmental sound memory."""
        return cls(
            sound_type="environmental",
            description=f"Sound of {source}",
            source=source,
            is_continuous=continuous,
            volume=0.4,
            clarity=0.7
        )

# --------------------------------------------------------------------
# 2. OlfactoryMemory (Smell)
# --------------------------------------------------------------------
@dataclass
class OlfactoryMemory:
    """
    Memory of a smell: floral, food, natural, chemical, etc.
    """
    scent_name: str = ""
    scent_category: str = "other"  # floral, fruity, woody, spicy, earthy, chemical, food, marine
    intensity: float = 0.5          # 0.0 (barely perceptible) to 1.0 (overwhelming)
    pleasantness: float = 0.5       # 0.0 (very unpleasant) to 1.0 (very pleasant)
    familiarity: float = 0.5        # 0.0 (unfamiliar) to 1.0 (very familiar)
    source: str = ""                # e.g., "rose", "coffee", "ocean"
    duration_seconds: float = 5.0
    emotional_association: str = ""  # e.g., "childhood", "nostalgia", "calm"
    
    def render(self) -> str:
        parts = []
        if not self.scent_name and not self.source:
            parts.append("I remember a smell, but cannot identify it.")
        else:
            name = self.scent_name if self.scent_name else self.source
            parts.append(f"I remember the smell of {name}.")
        
        # Intensity
        int_desc = "overwhelming" if self.intensity > 0.8 else "strong" if self.intensity > 0.6 else "moderate" if self.intensity > 0.3 else "faint"
        parts.append(f"It was {int_desc} (intensity {self.intensity:.2f}).")
        
        # Pleasantness
        if self.pleasantness > 0.7:
            parts.append("It was a very pleasant scent.")
        elif self.pleasantness < 0.3:
            parts.append("It was unpleasant.")
        
        # Familiarity
        if self.familiarity > 0.8:
            parts.append("It smelled very familiar.")
        elif self.familiarity < 0.2:
            parts.append("It was completely unfamiliar.")
        
        # Category
        category_names = {
            "floral": "floral", "fruity": "fruity", "woody": "woody", "spicy": "spicy",
            "earthy": "earthy", "chemical": "chemical", "food": "food", "marine": "marine"
        }
        if self.scent_category in category_names:
            parts.append(f"The scent was {category_names[self.scent_category]}.")
        
        # Duration
        if self.duration_seconds > 0:
            parts.append(f"It lingered for about {self.duration_seconds:.1f} seconds.")
        
        # Emotional association
        if self.emotional_association:
            parts.append(f"It reminded me of {self.emotional_association}.")
        
        return " ".join(parts)
    
    def to_dict(self) -> Dict:
        return {
            "type": "olfactory",
            "scent_name": self.scent_name,
            "scent_category": self.scent_category,
            "intensity": self.intensity,
            "pleasantness": self.pleasantness,
            "familiarity": self.familiarity,
            "source": self.source,
            "duration_seconds": self.duration_seconds,
            "emotional_association": self.emotional_association
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'OlfactoryMemory':
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)
    
    @classmethod
    def from_scent(cls, name: str, category: str = "other", pleasant: bool = True) -> 'OlfactoryMemory':
        """Factory: create a scent memory with default pleasantness."""
        return cls(
            scent_name=name,
            scent_category=category,
            pleasantness=0.8 if pleasant else 0.2,
            familiarity=0.6,
            source=name
        )
    
    @classmethod
    def from_food(cls, food_name: str) -> 'OlfactoryMemory':
        """Factory: create a food aroma memory."""
        return cls(
            scent_name=food_name,
            scent_category="food",
            pleasantness=0.85,
            familiarity=0.7,
            source="food",
            intensity=0.6
        )

# --------------------------------------------------------------------
# 3. GustatoryMemory (Taste)
# --------------------------------------------------------------------
@dataclass
class GustatoryMemory:
    """
    Memory of a taste: used for clone body enjoyment (eating/drinking).
    """
    flavor_name: str = ""
    dish_name: str = ""
    beverage_name: str = ""
    cuisine: str = ""
    
    # Basic tastes (0.0 to 1.0)
    sweetness: float = 0.0
    sourness: float = 0.0
    saltiness: float = 0.0
    bitterness: float = 0.0
    umami: float = 0.0
    spiciness: float = 0.0
    
    # Texture and temperature
    texture: str = "smooth"      # smooth, crunchy, chewy, creamy, crispy
    temperature_celsius: float = 20.0
    carbonated: bool = False
    
    # Enjoyment (for clone body pleasure)
    enjoyment_level: float = 0.5    # 0.0 (dislike) to 1.0 (love)
    is_favorite: bool = False
    times_enjoyed: int = 1
    
    # Context
    meal_type: str = ""           # breakfast, lunch, dinner, snack, dessert
    occasion: str = ""            # casual, celebration, daily
    shared_with: List[str] = field(default_factory=list)
    
    def render(self) -> str:
        parts = []
        if self.dish_name:
            parts.append(f"I remember the taste of {self.dish_name}.")
        elif self.beverage_name:
            parts.append(f"I remember the taste of {self.beverage_name}.")
        elif self.flavor_name:
            parts.append(f"I remember the taste of {self.flavor_name}.")
        else:
            parts.append("I remember a taste.")
        
        # Taste profile
        tastes = []
        if self.sweetness > 0.6:
            tastes.append("sweet")
        if self.sourness > 0.6:
            tastes.append("sour")
        if self.saltiness > 0.6:
            tastes.append("salty")
        if self.bitterness > 0.6:
            tastes.append("bitter")
        if self.umami > 0.6:
            tastes.append("savory (umami)")
        if self.spiciness > 0.6:
            tastes.append("spicy")
        
        if tastes:
            parts.append(f"It was {', '.join(tastes)}.")
        
        # Texture
        parts.append(f"The texture was {self.texture}.")
        
        # Temperature
        temp_desc = "hot" if self.temperature_celsius > 60 else "warm" if self.temperature_celsius > 30 else "cool" if self.temperature_celsius > 10 else "cold"
        parts.append(f"It was served {temp_desc} (about {self.temperature_celsius:.0f}°C).")
        
        if self.carbonated:
            parts.append("It was carbonated.")
        
        # Enjoyment
        if self.enjoyment_level > 0.8:
            parts.append("I really enjoyed it.")
        elif self.enjoyment_level > 0.6:
            parts.append("It was pleasant.")
        elif self.enjoyment_level < 0.3:
            parts.append("I did not enjoy it.")
        
        if self.is_favorite:
            parts.append("This is one of my favourite tastes.")
        
        if self.cuisine:
            parts.append(f"It was prepared in {self.cuisine} style.")
        
        if self.meal_type:
            parts.append(f"I had this during {self.meal_type}.")
        
        if self.occasion and self.occasion != "casual":
            parts.append(f"It was a {self.occasion} meal.")
        
        if self.shared_with:
            names = ", ".join(self.shared_with[:2])
            parts.append(f"I shared it with {names}.")
        
        return " ".join(parts)
    
    def to_dict(self) -> Dict:
        return {
            "type": "gustatory",
            "flavor_name": self.flavor_name,
            "dish_name": self.dish_name,
            "beverage_name": self.beverage_name,
            "cuisine": self.cuisine,
            "sweetness": self.sweetness,
            "sourness": self.sourness,
            "saltiness": self.saltiness,
            "bitterness": self.bitterness,
            "umami": self.umami,
            "spiciness": self.spiciness,
            "texture": self.texture,
            "temperature_celsius": self.temperature_celsius,
            "carbonated": self.carbonated,
            "enjoyment_level": self.enjoyment_level,
            "is_favorite": self.is_favorite,
            "times_enjoyed": self.times_enjoyed,
            "meal_type": self.meal_type,
            "occasion": self.occasion,
            "shared_with": self.shared_with
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'GustatoryMemory':
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)
    
    @classmethod
    def from_dish(cls, dish: str, cuisine: str = "", enjoyment: float = 0.7) -> 'GustatoryMemory':
        """Factory: create a taste memory from a dish."""
        return cls(
            dish_name=dish,
            cuisine=cuisine,
            enjoyment_level=enjoyment,
            texture="smooth",
            temperature_celsius=60 if "soup" in dish.lower() else 20
        )
    
    @classmethod
    def from_beverage(cls, beverage: str, temperature: float = 20.0, carbonated: bool = False) -> 'GustatoryMemory':
        """Factory: create a taste memory from a beverage."""
        return cls(
            beverage_name=beverage,
            temperature_celsius=temperature,
            carbonated=carbonated,
            enjoyment_level=0.6,
            texture="liquid"
        )
    
    @classmethod
    def from_sweet(cls, dessert: str, sweetness: float = 0.8, enjoyment: float = 0.9) -> 'GustatoryMemory':
        """Factory: create a sweet dessert memory."""
        return cls(
            dish_name=dessert,
            sweetness=sweetness,
            enjoyment_level=enjoyment,
            meal_type="dessert",
            texture="creamy"
        )


# --------------------------------------------------------------------
# Utility: random sensory memory (for testing)
# --------------------------------------------------------------------
def random_audio_memory() -> AudioMemory:
    """Create a random audio memory for testing."""
    choice = random.choice(["speech", "music", "environmental", "silence"])
    if choice == "speech":
        return AudioMemory.from_speech(
            text="Hello, this is a test.",
            speaker="Unknown",
            emotion=random.choice(["happy", "sad", "neutral", "angry"])
        )
    elif choice == "music":
        songs = ["Bohemian Rhapsody", "Imagine", "Shape of You", "Billie Jean"]
        return AudioMemory.from_music(
            title=random.choice(songs),
            artist="Various",
            genre=random.choice(["rock", "pop", "classical"])
        )
    elif choice == "environmental":
        sources = ["rain", "traffic", "birds chirping", "wind", "ocean waves"]
        return AudioMemory.from_environmental(source=random.choice(sources))
    else:
        return AudioMemory(sound_type="silence", description="Complete silence")

def random_olfactory_memory() -> OlfactoryMemory:
    """Create a random olfactory memory."""
    scents = ["rose", "coffee", "fresh bread", "ocean breeze", "pine forest", "vanilla", "lemon"]
    categories = ["floral", "food", "marine", "woody", "fruity"]
    return OlfactoryMemory(
        scent_name=random.choice(scents),
        scent_category=random.choice(categories),
        intensity=random.uniform(0.3, 0.9),
        pleasantness=random.uniform(0.4, 0.9),
        familiarity=random.uniform(0.2, 0.9)
    )

def random_gustatory_memory() -> GustatoryMemory:
    """Create a random taste memory."""
    dishes = ["pizza", "sushi", "ice cream", "curry", "pasta", "chocolate cake", "coffee"]
    return GustatoryMemory.from_dish(
        dish=random.choice(dishes),
        enjoyment=random.uniform(0.4, 0.95)
    )

# ====================================================================================================
# Example usage (commented)
# ====================================================================================================
"""
# Audio examples
speech = AudioMemory.from_speech("Hello world!", "Alice", "happy")
print(speech.render())

music = AudioMemory.from_music("Bohemian Rhapsody", "Queen", "rock")
print(music.render())

# Olfactory example
coffee = OlfactoryMemory.from_scent("Fresh coffee", "food", pleasant=True)
print(coffee.render())

# Gustatory example
pizza = GustatoryMemory.from_dish("Margherita pizza", "Italian", enjoyment=0.9)
pizza.texture = "crispy"
pizza.shared_with = ["friend"]
print(pizza.render())
"""

# ====================================================================================================
# END OF multimodal_sensory.py (32,478 characters)
# ====================================================================================================
