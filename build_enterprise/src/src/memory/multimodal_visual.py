# ====================================================================================================
# multimodal_visual.py – Multimodal Visual Memory Classes for CrownStar‑Absolute
# Implements:
#   - SunlitImage: outdoor scenes with natural lighting
#   - InteriorScene: indoor spaces, rooms, buildings
#   - VehicleInterior: car, train, aircraft, spacecraft interiors
#   - ExteriorScene: urban, rural, night, weather scenes
# ====================================================================================================

import random
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
import time

# --------------------------------------------------------------------
# Base Visual Memory Class
# --------------------------------------------------------------------
class VisualMemory:
    """Base class for all visual memories."""
    
    def render(self) -> str:
        """Return a textual description of the visual memory."""
        raise NotImplementedError
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialisation."""
        raise NotImplementedError
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'VisualMemory':
        """Reconstruct from dictionary."""
        raise NotImplementedError

# --------------------------------------------------------------------
# 1. SunlitImage (Outdoor, natural light)
# --------------------------------------------------------------------
@dataclass
class SunlitImage(VisualMemory):
    """
    Vivid sunlit outdoor memory with strong natural lighting.
    """
    scene_description: str = ""
    location: str = ""
    terrain: str = "field"          # field, beach, forest, mountain, urban
    time_of_day: str = "afternoon"  # dawn, morning, afternoon, golden_hour, dusk, night
    season: str = "summer"          # spring, summer, autumn, winter
    sky_condition: str = "clear"    # clear, partly_cloudy, overcast, hazy
    cloud_cover: float = 0.2
    light_intensity: float = 0.8    # 0.0 - 1.0
    sun_angle: float = 45.0         # degrees
    shadow_softness: float = 0.5
    color_saturation: float = 0.7
    color_temperature: str = "neutral"  # warm, neutral, cool
    vegetation: List[str] = field(default_factory=list)
    has_water: bool = False
    water_type: str = "none"        # ocean, lake, river, pond
    has_birds: bool = False
    has_rainbow: bool = False
    has_haze: bool = False
    haze_density: float = 0.0
    temperature_celsius: float = 22.0
    wind_speed: float = 5.0
    wind_direction: str = "calm"
    
    def render(self) -> str:
        """Generate a rich textual description of the sunlit scene."""
        parts = []
        # Time and season
        parts.append(f"It is {self.time_of_day.replace('_', ' ')} in {self.season}.")
        # Sky
        sky_desc = {
            "clear": "crisp and clear",
            "partly_cloudy": "partly cloudy",
            "overcast": "overcast",
            "hazy": "slightly hazy"
        }.get(self.sky_condition, "clear")
        parts.append(f"The sky is {sky_desc} with {int(self.cloud_cover*100)}% cloud cover.")
        # Lighting
        light_desc = "bright" if self.light_intensity > 0.7 else "moderate" if self.light_intensity > 0.4 else "soft"
        temp_desc = {"warm": "warm golden", "neutral": "neutral", "cool": "cool blue"}.get(self.color_temperature, "neutral")
        parts.append(f"The light is {light_desc} and {temp_desc}, with the sun at {self.sun_angle:.0f}° elevation.")
        if self.shadow_softness > 0.7:
            parts.append("Shadows are very soft and diffuse.")
        elif self.shadow_softness < 0.3:
            parts.append("Shadows are sharp and well-defined.")
        # Terrain and location
        parts.append(f"I am standing in {self.location if self.location else 'an open area'} with {self.terrain} terrain.")
        # Vegetation
        if self.vegetation:
            veg_str = ", ".join(self.vegetation[:3])
            parts.append(f"There is {veg_str} vegetation.")
        # Water
        if self.has_water and self.water_type != "none":
            water_names = {"ocean": "the ocean", "lake": "a lake", "river": "a river", "pond": "a pond"}
            parts.append(f"Nearby, {water_names.get(self.water_type, 'water')} glistens.")
        # Weather
        if self.has_haze:
            parts.append("A light haze softens the distance.")
        if self.has_rainbow:
            parts.append("A rainbow arcs across the sky.")
        if self.has_birds:
            parts.append("Birds are visible in the distance.")
        # Temperature and wind
        parts.append(f"The temperature feels around {self.temperature_celsius:.0f}°C, with {self.wind_speed:.0f} km/h wind from the {self.wind_direction}.")
        # Main description
        if self.scene_description:
            parts.append(self.scene_description)
        return " ".join(parts)
    
    def to_dict(self) -> Dict:
        return {
            "type": "sunlit",
            "scene_description": self.scene_description,
            "location": self.location,
            "terrain": self.terrain,
            "time_of_day": self.time_of_day,
            "season": self.season,
            "sky_condition": self.sky_condition,
            "cloud_cover": self.cloud_cover,
            "light_intensity": self.light_intensity,
            "sun_angle": self.sun_angle,
            "shadow_softness": self.shadow_softness,
            "color_saturation": self.color_saturation,
            "color_temperature": self.color_temperature,
            "vegetation": self.vegetation,
            "has_water": self.has_water,
            "water_type": self.water_type,
            "has_birds": self.has_birds,
            "has_rainbow": self.has_rainbow,
            "has_haze": self.has_haze,
            "haze_density": self.haze_density,
            "temperature_celsius": self.temperature_celsius,
            "wind_speed": self.wind_speed,
            "wind_direction": self.wind_direction
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SunlitImage':
        return cls(
            scene_description=data.get("scene_description", ""),
            location=data.get("location", ""),
            terrain=data.get("terrain", "field"),
            time_of_day=data.get("time_of_day", "afternoon"),
            season=data.get("season", "summer"),
            sky_condition=data.get("sky_condition", "clear"),
            cloud_cover=data.get("cloud_cover", 0.2),
            light_intensity=data.get("light_intensity", 0.8),
            sun_angle=data.get("sun_angle", 45.0),
            shadow_softness=data.get("shadow_softness", 0.5),
            color_saturation=data.get("color_saturation", 0.7),
            color_temperature=data.get("color_temperature", "neutral"),
            vegetation=data.get("vegetation", []),
            has_water=data.get("has_water", False),
            water_type=data.get("water_type", "none"),
            has_birds=data.get("has_birds", False),
            has_rainbow=data.get("has_rainbow", False),
            has_haze=data.get("has_haze", False),
            haze_density=data.get("haze_density", 0.0),
            temperature_celsius=data.get("temperature_celsius", 22.0),
            wind_speed=data.get("wind_speed", 5.0),
            wind_direction=data.get("wind_direction", "calm")
        )

# --------------------------------------------------------------------
# 2. InteriorScene (Indoor spaces)
# --------------------------------------------------------------------
@dataclass
class InteriorScene(VisualMemory):
    """
    Memory of an indoor space: room, building, etc.
    """
    room_type: str = "living_room"   # living_room, kitchen, bedroom, office, library, restaurant
    building_type: str = "house"     # house, apartment, office_building, school, hospital
    lighting_type: str = "artificial"  # artificial, natural, mixed
    lighting_brightness: float = 0.6
    lighting_color: str = "warm"
    has_windows: bool = True
    window_count: int = 1
    window_orientation: str = "south"
    furnishings: List[str] = field(default_factory=list)
    decorative_objects: List[str] = field(default_factory=list)
    floor_material: str = "wood"
    wall_color: str = "white"
    ceiling_height: float = 2.5  # meters
    is_open_plan: bool = False
    people_present: int = 0
    atmosphere: str = "neutral"  # cozy, sterile, cluttered, spacious
    temperature_celsius: float = 21.0
    humidity: float = 0.5
    sound_level: float = 0.3  # 0.0 silent, 1.0 loud
    ambient_sound: str = "quiet"
    
    def render(self) -> str:
        parts = []
        parts.append(f"I am in a {self.room_type.replace('_', ' ')} inside a {self.building_type.replace('_', ' ')}.")
        # Lighting
        light_type_str = {"artificial": "artificial lighting", "natural": "natural light", "mixed": "mixed lighting"}.get(self.lighting_type, "lighting")
        brightness_str = "bright" if self.lighting_brightness > 0.7 else "moderate" if self.lighting_brightness > 0.4 else "dim"
        parts.append(f"The {light_type_str} is {brightness_str} and {self.lighting_color} in colour.")
        if self.has_windows:
            parts.append(f"There { 'are' if self.window_count > 1 else 'is'} {self.window_count} window(s) facing {self.window_orientation}.")
        # Furnishings
        if self.furnishings:
            furn_str = ", ".join(self.furnishings[:5])
            parts.append(f"The room contains {furn_str}.")
        if self.decorative_objects:
            dec_str = ", ".join(self.decorative_objects[:3])
            parts.append(f"I notice {dec_str}.")
        # Architecture
        parts.append(f"The floor is {self.floor_material}, the walls are {self.wall_color}, and the ceiling is {self.ceiling_height:.1f} meters high.")
        if self.is_open_plan:
            parts.append("The space is open plan.")
        # People
        if self.people_present > 0:
            parts.append(f"There { 'are' if self.people_present > 1 else 'is'} {self.people_present} person(s) in the room.")
        # Atmosphere
        parts.append(f"The atmosphere is {self.atmosphere}, with a temperature of {self.temperature_celsius:.0f}°C.")
        if self.sound_level > 0.7:
            parts.append("It is quite loud.")
        elif self.sound_level < 0.2:
            parts.append("It is very quiet.")
        if self.ambient_sound and self.ambient_sound != "quiet":
            parts.append(f"I can hear {self.ambient_sound} in the background.")
        return " ".join(parts)
    
    def to_dict(self) -> Dict:
        return {
            "type": "interior",
            "room_type": self.room_type,
            "building_type": self.building_type,
            "lighting_type": self.lighting_type,
            "lighting_brightness": self.lighting_brightness,
            "lighting_color": self.lighting_color,
            "has_windows": self.has_windows,
            "window_count": self.window_count,
            "window_orientation": self.window_orientation,
            "furnishings": self.furnishings,
            "decorative_objects": self.decorative_objects,
            "floor_material": self.floor_material,
            "wall_color": self.wall_color,
            "ceiling_height": self.ceiling_height,
            "is_open_plan": self.is_open_plan,
            "people_present": self.people_present,
            "atmosphere": self.atmosphere,
            "temperature_celsius": self.temperature_celsius,
            "humidity": self.humidity,
            "sound_level": self.sound_level,
            "ambient_sound": self.ambient_sound
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'InteriorScene':
        return cls(**data)

# --------------------------------------------------------------------
# 3. VehicleInterior (Cars, trains, aircraft, spacecraft)
# --------------------------------------------------------------------
@dataclass
class VehicleInterior(VisualMemory):
    """
    Memory from inside a moving or stationary vehicle.
    """
    vehicle_type: str = "car"          # car, truck, bus, train, aircraft, spacecraft
    make: str = ""
    model: str = ""
    seat_position: str = "driver"      # driver, passenger_front, passenger_rear, pilot
    is_moving: bool = True
    speed_kmh: float = 60.0
    view_direction: str = "forward"    # forward, left, right, rear
    view_description: str = ""
    dashboard_elements: List[str] = field(default_factory=list)
    warning_lights: List[str] = field(default_factory=list)
    has_navigation: bool = False
    navigation_display: str = ""
    radio_playing: bool = False
    radio_station: str = ""
    passenger_count: int = 0
    is_night: bool = False
    is_raining: bool = False
    window_tinted: bool = False
    seat_material: str = "cloth"
    temperature_celsius: float = 22.0
    vibration_level: float = 0.2
    road_condition: str = "smooth"     # smooth, bumpy, wet, icy
    
    def render(self) -> str:
        parts = []
        vehicle_name = f"{self.make} {self.model}" if self.make and self.model else self.vehicle_type
        parts.append(f"I am inside a {vehicle_name}, sitting in the {self.seat_position.replace('_', ' ')} seat.")
        if self.is_moving:
            parts.append(f"The vehicle is moving at approximately {self.speed_kmh:.0f} km/h.")
            parts.append(f"The ride feels {self.road_condition} with vibration level {self.vibration_level:.1f}.")
        else:
            parts.append("The vehicle is stationary.")
        # View
        view_dir = {"forward": "ahead", "left": "to the left", "right": "to the right", "rear": "behind"}
        parts.append(f"Looking {view_dir.get(self.view_direction, self.view_direction)}, I see {self.view_description if self.view_description else 'the road ahead'}.")
        if self.is_night:
            parts.append("It is dark outside.")
        if self.is_raining:
            parts.append("Rain is falling, streaking across the windows.")
        # Dashboard
        if self.dashboard_elements:
            dash_str = ", ".join(self.dashboard_elements[:5])
            parts.append(f"The dashboard shows {dash_str}.")
        if self.warning_lights:
            parts.append(f"Warning lights: {', '.join(self.warning_lights)}.")
        if self.has_navigation:
            parts.append(f"Navigation displays: {self.navigation_display}.")
        # Audio
        if self.radio_playing:
            parts.append(f"The radio is playing {self.radio_station or 'music'}.")
        # Passengers
        if self.passenger_count > 0:
            parts.append(f"There { 'are' if self.passenger_count > 1 else 'is'} {self.passenger_count} passenger(s) with me.")
        # Comfort
        parts.append(f"Temperature inside is {self.temperature_celsius:.0f}°C, seats are {self.seat_material}.")
        return " ".join(parts)
    
    def to_dict(self) -> Dict:
        return {
            "type": "vehicle",
            "vehicle_type": self.vehicle_type,
            "make": self.make,
            "model": self.model,
            "seat_position": self.seat_position,
            "is_moving": self.is_moving,
            "speed_kmh": self.speed_kmh,
            "view_direction": self.view_direction,
            "view_description": self.view_description,
            "dashboard_elements": self.dashboard_elements,
            "warning_lights": self.warning_lights,
            "has_navigation": self.has_navigation,
            "navigation_display": self.navigation_display,
            "radio_playing": self.radio_playing,
            "radio_station": self.radio_station,
            "passenger_count": self.passenger_count,
            "is_night": self.is_night,
            "is_raining": self.is_raining,
            "window_tinted": self.window_tinted,
            "seat_material": self.seat_material,
            "temperature_celsius": self.temperature_celsius,
            "vibration_level": self.vibration_level,
            "road_condition": self.road_condition
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'VehicleInterior':
        return cls(**data)

# --------------------------------------------------------------------
# 4. ExteriorScene (Urban, natural, weather, night)
# --------------------------------------------------------------------
@dataclass
class ExteriorScene(VisualMemory):
    """
    Outdoor scene that is not specifically sunlit – includes urban, night, weather.
    """
    location_type: str = "urban"       # urban, suburban, rural, wilderness
    environment: str = "city"          # city, forest, mountain, desert, coastal
    time_of_day: str = "day"           # dawn, day, dusk, night
    weather: str = "clear"             # clear, cloudy, rain, snow, fog, storm
    temperature_celsius: float = 20.0
    wind_speed: float = 5.0
    precipitation_intensity: float = 0.0
    visibility_km: float = 10.0
    buildings: List[str] = field(default_factory=list)
    landmarks: List[str] = field(default_factory=list)
    vegetation: List[str] = field(default_factory=list)
    has_street_lights: bool = False
    has_traffic: bool = False
    people_count: int = 0
    is_night: bool = False
    moon_phase: float = 0.5            # 0=new, 1=full
    stars_visible: bool = False
    star_visibility: int = 0            # 0-10
    dominant_sound: str = "traffic"    # traffic, birds, wind, silence, waves
    smell: str = "neutral"             # neutral, fresh, polluted, sea, pine
    
    def render(self) -> str:
        parts = []
        parts.append(f"I am in a {self.location_type} {self.environment} environment.")
        # Time
        if self.is_night:
            parts.append("It is night time.")
            if self.moon_phase > 0.7:
                parts.append("The moon is nearly full.")
            elif self.moon_phase > 0.3:
                parts.append("A crescent moon is visible.")
            if self.stars_visible:
                parts.append(f"Stars are { 'clearly' if self.star_visibility > 7 else 'faintly' } visible.")
        else:
            parts.append(f"It is {self.time_of_day}.")
        # Weather
        weather_desc = {
            "clear": "clear", "cloudy": "cloudy", "rain": "raining", "snow": "snowing", "fog": "foggy", "storm": "stormy"
        }.get(self.weather, "clear")
        parts.append(f"The weather is {weather_desc}.")
        if self.precipitation_intensity > 0:
            intensity_str = "lightly" if self.precipitation_intensity < 0.3 else "moderately" if self.precipitation_intensity < 0.7 else "heavily"
            parts.append(f"It is {intensity_str} {self.weather}.")
        parts.append(f"Temperature is {self.temperature_celsius:.0f}°C, wind at {self.wind_speed:.0f} km/h.")
        parts.append(f"Visibility is {self.visibility_km:.1f} km.")
        # Urban vs natural
        if self.location_type == "urban":
            if self.buildings:
                building_str = ", ".join(self.buildings[:3])
                parts.append(f"Buildings include {building_str}.")
            if self.landmarks:
                parts.append(f"I can see {self.landmarks[0]}.")
            if self.has_street_lights:
                parts.append("Street lights illuminate the area.")
            if self.has_traffic:
                parts.append("Traffic is flowing on the roads.")
        else:
            if self.vegetation:
                veg_str = ", ".join(self.vegetation[:3])
                parts.append(f"Vegetation: {veg_str}.")
        # People
        if self.people_count > 0:
            parts.append(f"There { 'are' if self.people_count > 1 else 'is'} {self.people_count} person(s) around.")
        # Sounds
        parts.append(f"The dominant sound is {self.dominant_sound}.")
        # Smell
        if self.smell != "neutral":
            parts.append(f"The air smells {self.smell}.")
        return " ".join(parts)
    
    def to_dict(self) -> Dict:
        return {
            "type": "exterior",
            "location_type": self.location_type,
            "environment": self.environment,
            "time_of_day": self.time_of_day,
            "weather": self.weather,
            "temperature_celsius": self.temperature_celsius,
            "wind_speed": self.wind_speed,
            "precipitation_intensity": self.precipitation_intensity,
            "visibility_km": self.visibility_km,
            "buildings": self.buildings,
            "landmarks": self.landmarks,
            "vegetation": self.vegetation,
            "has_street_lights": self.has_street_lights,
            "has_traffic": self.has_traffic,
            "people_count": self.people_count,
            "is_night": self.is_night,
            "moon_phase": self.moon_phase,
            "stars_visible": self.stars_visible,
            "star_visibility": self.star_visibility,
            "dominant_sound": self.dominant_sound,
            "smell": self.smell
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ExteriorScene':
        return cls(**data)


# --------------------------------------------------------------------
# Utility: create a random visual memory (for testing)
# --------------------------------------------------------------------
def random_visual_memory() -> VisualMemory:
    """Create a random visual memory for testing or simulation."""
    import random
    choice = random.choice(["sunlit", "interior", "vehicle", "exterior"])
    if choice == "sunlit":
        return SunlitImage(
            scene_description="A beautiful landscape.",
            location=random.choice(["beach", "forest", "mountain", "field"]),
            time_of_day=random.choice(["morning", "afternoon", "golden_hour"]),
            season=random.choice(["spring", "summer", "autumn"]),
            sky_condition=random.choice(["clear", "partly_cloudy"]),
            has_water=random.choice([True, False])
        )
    elif choice == "interior":
        return InteriorScene(
            room_type=random.choice(["living_room", "kitchen", "office", "library"]),
            lighting_type=random.choice(["artificial", "natural", "mixed"]),
            furnishings=["sofa", "table", "lamp"],
            people_present=random.randint(0, 3)
        )
    elif choice == "vehicle":
        return VehicleInterior(
            vehicle_type=random.choice(["car", "train", "aircraft"]),
            is_moving=True,
            speed_kmh=random.uniform(50, 120),
            view_description=random.choice(["highway", "city streets", "clouds", "tracks"]),
            radio_playing=True
        )
    else:
        return ExteriorScene(
            location_type=random.choice(["urban", "rural"]),
            weather=random.choice(["clear", "rain", "cloudy"]),
            buildings=["office tower", "apartment"] if random.choice([True, False]) else [],
            has_traffic=random.choice([True, False])
        )

# ====================================================================================================
# Example usage (commented)
# ====================================================================================================
"""
# Create a sunny beach memory
beach = SunlitImage(
    scene_description="Waves gently lapping at the shore.",
    location="Tropical beach",
    terrain="beach",
    time_of_day="golden_hour",
    season="summer",
    sky_condition="clear",
    has_water=True,
    water_type="ocean",
    has_birds=True,
    temperature_celsius=28.0,
    wind_speed=8.0
)
print(beach.render())

# Create a vehicle interior memory
car = VehicleInterior(
    vehicle_type="car",
    make="Tesla",
    model="Model 3",
    seat_position="driver",
    speed_kmh=110,
    view_description="a winding coastal road",
    dashboard_elements=["speedometer", "navigation", "battery gauge"],
    radio_playing=True,
    radio_station="classic rock",
    passenger_count=1,
    is_moving=True
)
print(car.render())
"""

# ====================================================================================================
# END OF multimodal_visual.py (31,567 characters)
# ====================================================================================================
