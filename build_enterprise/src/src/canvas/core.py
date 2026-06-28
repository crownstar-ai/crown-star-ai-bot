# canvas/core.py – CrownStar Generative UI & Real‑Time Collaboration Engine
import os, json, time, uuid, base64, threading, hashlib
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from collections import deque
import logging
import numpy as np
from PIL import Image, ImageDraw, ImageOps
import io

logger = logging.getLogger(__name__)

@dataclass
class CanvasStroke:
    id: str
    points: List[Tuple[int, int]]
    color: str
    width: int
    timestamp: int

@dataclass
class CanvasLayer:
    id: str
    name: str
    strokes: List[CanvasStroke]
    z_index: int
    visible: bool = True

@dataclass
class CanvasState:
    canvas_id: str
    width: int
    height: int
    background_color: str
    layers: List[CanvasLayer]
    version: int
    last_modified: int
    created_by: str

@dataclass
class CanvasSnapshot:
    canvas_id: str
    version: int
    state: CanvasState
    embedding: Optional[List[float]] = None

class CanvasRenderer:
    @staticmethod
    def render_to_pil(state: CanvasState) -> Image.Image:
        img = Image.new("RGB", (state.width, state.height), color=state.background_color)
        draw = ImageDraw.Draw(img)
        for layer in sorted(state.layers, key=lambda l: l.z_index):
            if not layer.visible:
                continue
            for stroke in layer.strokes:
                if len(stroke.points) < 2:
                    continue
                for i in range(len(stroke.points) - 1):
                    draw.line(
                        stroke.points[i] + stroke.points[i+1],
                        fill=stroke.color,
                        width=stroke.width
                    )
        return img

    @staticmethod
    def render_to_base64(state: CanvasState) -> str:
        img = CanvasRenderer.render_to_pil(state)
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()

    @staticmethod
    def render_to_svg(state: CanvasState) -> str:
        svg_lines = []
        svg_lines.append(f'<svg width="{state.width}" height="{state.height}" xmlns="http://www.w3.org/2000/svg">')
        svg_lines.append(f'<rect width="100%" height="100%" fill="{state.background_color}"/>')
        for layer in sorted(state.layers, key=lambda l: l.z_index):
            if not layer.visible:
                continue
            for stroke in layer.strokes:
                if len(stroke.points) < 2:
                    continue
                points_str = " ".join([f"{x},{y}" for x, y in stroke.points])
                svg_lines.append(f'<polyline points="{points_str}" stroke="{stroke.color}" stroke-width="{stroke.width}" fill="none"/>')
        svg_lines.append("</svg>")
        return "\n".join(svg_lines)

class GenerativeCanvasAI:
    def __init__(self):
        self._mm = None

    def _get_mm(self):
        if self._mm is None:
            try:
                from multimodal.core import get_mm_manager
                self._mm = get_mm_manager()
            except ImportError:
                logger.warning("Multi‑modal not available, using dummy generator")
        return self._mm

    def text_to_sketch(self, prompt: str, width: int = 800, height: int = 600) -> CanvasState:
        state = CanvasState(
            canvas_id=f"gen_{uuid.uuid4().hex[:8]}",
            width=width,
            height=height,
            background_color="#ffffff",
            layers=[],
            version=1,
            last_modified=int(time.time()),
            created_by="generative_ai"
        )
        strokes = []
        words = prompt.lower().split()
        if "circle" in words or "sun" in words:
            strokes.append(self._make_circle(width//2, height//2, 100, "#FFD700", 3))
        if "square" in words or "house" in words:
            strokes.append(self._make_rectangle(width//4, height//4, width//2, height//2, "#8B4513", 4))
        if "line" in words or "path" in words:
            strokes.append(self._make_line(50, 50, width-50, height-50, "#000000", 2))
        state.layers.append(CanvasLayer(
            id=str(uuid.uuid4()),
            name="generated",
            strokes=strokes,
            z_index=0,
            visible=True
        ))
        return state

    def _make_circle(self, cx, cy, r, color, width):
        points = []
        for angle in range(0, 360, 10):
            x = int(cx + r * np.cos(np.radians(angle)))
            y = int(cy + r * np.sin(np.radians(angle)))
            points.append((x, y))
        return CanvasStroke(id=str(uuid.uuid4()), points=points, color=color, width=width, timestamp=int(time.time()))

    def _make_rectangle(self, x1, y1, x2, y2, color, width):
        points = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
        return CanvasStroke(id=str(uuid.uuid4()), points=points, color=color, width=width, timestamp=int(time.time()))

    def _make_line(self, x1, y1, x2, y2, color, width):
        points = [(x1, y1), (x2, y2)]
        return CanvasStroke(id=str(uuid.uuid4()), points=points, color=color, width=width, timestamp=int(time.time()))

    def complete_drawing(self, state: CanvasState, prompt: str = None) -> CanvasState:
        return state

    def generate_similar(self, state: CanvasState) -> CanvasState:
        return state

class CollaborationManager:
    def __init__(self):
        self._rooms: Dict[str, List] = {}
        self._pending_ops: Dict[str, deque] = {}
        self._lock = threading.Lock()

    def join_room(self, canvas_id: str, websocket):
        with self._lock:
            if canvas_id not in self._rooms:
                self._rooms[canvas_id] = []
                self._pending_ops[canvas_id] = deque(maxlen=1000)
            self._rooms[canvas_id].append(websocket)

    def leave_room(self, canvas_id: str, websocket):
        with self._lock:
            if canvas_id in self._rooms:
                self._rooms[canvas_id].remove(websocket)
                if not self._rooms[canvas_id]:
                    del self._rooms[canvas_id]
                    del self._pending_ops[canvas_id]

    def broadcast(self, canvas_id: str, message: Dict, exclude_websocket=None):
        if canvas_id not in self._rooms:
            return
        for client in self._rooms[canvas_id]:
            if client != exclude_websocket:
                try:
                    client.send(json.dumps(message))
                except Exception as e:
                    logger.error(f"Broadcast error: {e}")

    def store_operation(self, canvas_id: str, op: Dict):
        if canvas_id in self._pending_ops:
            self._pending_ops[canvas_id].append(op)
            while len(self._pending_ops[canvas_id]) > 1000:
                self._pending_ops[canvas_id].popleft()

    def get_history(self, canvas_id: str, limit: int = 100) -> List[Dict]:
        if canvas_id not in self._pending_ops:
            return []
        return list(self._pending_ops[canvas_id])[-limit:]

class CanvasManager:
    def __init__(self, storage_dir="data/canvas"):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        self.collab = CollaborationManager()
        self.generative = GenerativeCanvasAI()

    def _save_state(self, state: CanvasState):
        path = os.path.join(self.storage_dir, f"{state.canvas_id}.json")
        with open(path, 'w') as f:
            json.dump(asdict(state), f, indent=2)

    def _load_state(self, canvas_id: str) -> Optional[CanvasState]:
        path = os.path.join(self.storage_dir, f"{canvas_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, 'r') as f:
            data = json.load(f)
        layers = []
        for l in data.get("layers", []):
            strokes = [CanvasStroke(**s) for s in l.get("strokes", [])]
            layers.append(CanvasLayer(
                id=l["id"],
                name=l["name"],
                strokes=strokes,
                z_index=l["z_index"],
                visible=l.get("visible", True)
            ))
        return CanvasState(
            canvas_id=data["canvas_id"],
            width=data["width"],
            height=data["height"],
            background_color=data["background_color"],
            layers=layers,
            version=data["version"],
            last_modified=data["last_modified"],
            created_by=data["created_by"]
        )

    def create_canvas(self, width: int = 800, height: int = 600, background: str = "#ffffff", created_by: str = "user") -> CanvasState:
        canvas_id = str(uuid.uuid4())
        state = CanvasState(
            canvas_id=canvas_id,
            width=width,
            height=height,
            background_color=background,
            layers=[],
            version=1,
            last_modified=int(time.time()),
            created_by=created_by
        )
        self._save_state(state)
        return state

    def add_stroke(self, canvas_id: str, stroke: CanvasStroke) -> CanvasState:
        state = self._load_state(canvas_id)
        if not state:
            raise ValueError("Canvas not found")
        if not state.layers:
            default_layer = CanvasLayer(id=str(uuid.uuid4()), name="Layer 1", strokes=[], z_index=0, visible=True)
            state.layers.append(default_layer)
        state.layers[0].strokes.append(stroke)
        state.version += 1
        state.last_modified = int(time.time())
        self._save_state(state)
        self.collab.broadcast(canvas_id, {"type": "stroke", "stroke": asdict(stroke)})
        return state

    def undo(self, canvas_id: str) -> CanvasState:
        state = self._load_state(canvas_id)
        if not state or not state.layers:
            return state
        if state.layers[0].strokes:
            state.layers[0].strokes.pop()
            state.version += 1
            state.last_modified = int(time.time())
            self._save_state(state)
            self.collab.broadcast(canvas_id, {"type": "undo"})
        return state

    def generate_from_text(self, prompt: str, width: int = 800, height: int = 600) -> CanvasState:
        return self.generative.text_to_sketch(prompt, width, height)

    def get_canvas(self, canvas_id: str) -> Optional[CanvasState]:
        return self._load_state(canvas_id)

    def get_snapshot_embedding(self, canvas_id: str) -> Optional[List[float]]:
        state = self._load_state(canvas_id)
        if not state:
            return None
        img_b64 = CanvasRenderer.render_to_base64(state)
        mm = self.generative._get_mm()
        if mm:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(base64.b64decode(img_b64))
                tmp.flush()
                emb = mm.embed_image(tmp.name)
            os.unlink(tmp.name)
            return emb
        return None

_canvas_manager = None
def get_canvas_manager():
    global _canvas_manager
    if _canvas_manager is None:
        _canvas_manager = CanvasManager()
    return _canvas_manager
