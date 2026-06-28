# crownstar_core.py – Final version with vector memory and model router
import os, sys, json, time, asyncio, logging, sqlite3, datetime
import sys
import os

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

from typing import Dict, List, Optional

log = logging.getLogger("CrownStar.Core")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class HardwareProfile:
    def __init__(self):
        self.cpu_count = os.cpu_count() or 1
        self.total_ram_gb = 0
        self.has_gpu = False
        self.gpu_name = ""
        self.gpu_memory_gb = 0
        try:
            import psutil
            self.total_ram_gb = psutil.virtual_memory().total / (1024**3)
        except: pass
        try:
            import torch
            if torch.cuda.is_available():
                self.has_gpu = True
                self.gpu_name = torch.cuda.get_device_name(0)
                self.gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        except: pass

class CrownStarMathModules:
    def __init__(self, config_path=None):
        self.modules_state = {
            "base_3layer_jacobian": False, "hessian_backprop": False, "universal_approx": False,
            "gurney_3stage": False, "yegnanarayana_tensor": False, "haykin_recursive": False,
            "bishop_probabilistic": False, "zurada_indexed": False, "ultra_super_model": False
        }
        if config_path and os.path.exists(config_path):
            with open(config_path) as f:
                cfg = json.load(f)
                for k,v in cfg.get("module_toggles",{}).items():
                    if k in self.modules_state:
                        self.modules_state[k] = v
    def set_module(self, name: str, enabled: bool):
        if name in self.modules_state:
            self.modules_state[name] = enabled
            log.info(f"Module {name} set to {enabled}")
    def get_active(self) -> List[str]:
        return [k for k,v in self.modules_state.items() if v]
    def apply_preprocessing(self, prompt: str, query: str) -> str:
        if self.modules_state["base_3layer_jacobian"]:
            prompt = "[Jacobian‑aware] Consider sensitivity of output to input.\n" + prompt
        if self.modules_state["hessian_backprop"]:
            prompt = "[Second‑order optimization active] Use curvature.\n" + prompt
        if self.modules_state["universal_approx"]:
            prompt = "[UAT guarantee] Network can approximate any continuous function.\n" + prompt
        if self.modules_state["gurney_3stage"]:
            prompt = "[Gurney: linear → activation → output mapping]\n" + prompt
        if self.modules_state["yegnanarayana_tensor"]:
            prompt = "[Yegnanarayana: tensor composition of affine maps]\n" + prompt
        if self.modules_state["haykin_recursive"]:
            prompt = "[Haykin: recursive multi‑layer signal processing]\n" + prompt
        if self.modules_state["bishop_probabilistic"]:
            prompt = "[Bishop: probabilistic interpretation with softmax]\n" + prompt
        if self.modules_state["zurada_indexed"]:
            prompt = "[Zurada: explicit index summations]\n" + prompt
        if self.modules_state["ultra_super_model"]:
            prompt = "[CrownStar Ultra: all authors combined]\n" + prompt
        return prompt
    def apply_postprocessing(self, response: str) -> str:
        footnotes = []
        if self.modules_state["base_3layer_jacobian"]:
            footnotes.append("Jacobian sensitivity considered.")
        if self.modules_state["hessian_backprop"]:
            footnotes.append("Second‑order optimisation applied.")
        if footnotes:
            response += "\n\n(Note: " + " ".join(footnotes) + ")"
        return response

class CrownStarMemory:
    def __init__(self, db_path="data/conversations/crownstar_memory.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute('''CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, tier TEXT, user_message TEXT, assistant_message TEXT,
            modules_active TEXT, language_model TEXT, latency_ms INTEGER
        )''')
        self.conn.commit()
    def store(self, user_msg: str, assistant_msg: str, tier: str, modules: List[str], lang_model: str, latency_ms: int) -> int:
        ts = datetime.datetime.utcnow().isoformat()
        cur = self.conn.cursor()
        cur.execute('''INSERT INTO conversations
            (timestamp, tier, user_message, assistant_message, modules_active, language_model, latency_ms)
            VALUES (?,?,?,?,?,?,?)''',
            (ts, tier, user_msg, assistant_msg, ",".join(modules), lang_model, latency_ms))
        self.conn.commit()
        return cur.lastrowid
    def get_full_history(self, limit: int = None) -> List[Dict]:
        sql = "SELECT timestamp, user_message, assistant_message FROM conversations ORDER BY timestamp ASC"
        if limit: sql += f" LIMIT {limit}"
        cur = self.conn.execute(sql)
        return [{"timestamp": r[0], "user": r[1], "assistant": r[2]} for r in cur.fetchall()]

class CrownStarCore:
    def __init__(self, config_path="config/crownstar_config.json"):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        self.tier = os.environ.get("CROWNSTAR_TIER", "free_pay_per_use")
        self.hardware = HardwareProfile()
        self.modules = CrownStarMathModules(config_path)
        self.memory = CrownStarMemory()
        from memory.vector_memory import CrownStarVectorMemory
        self.vector_memory = CrownStarVectorMemory()
        from language_models.model_router import ModelRouter
        self.model_router = ModelRouter(default_model="deepseek_v2_lite")
        self.current_model = None
        log.info(f"CrownStar Core v{self.config['version']} initialised. Tier: {self.tier}")
    def set_module(self, name: str, enabled: bool):
        self.modules.set_module(name, enabled)
    def set_tier(self, tier: str):
        if tier in self.config["tiers"]:
            self.tier = tier
            log.info(f"Tier changed to {tier}")
        else:
            raise ValueError(f"Invalid tier: {tier}")
    def set_model(self, model_name: str):
        if model_name in self.model_router.list_models():
            self.current_model = model_name
            log.info(f"Language model set to {model_name}")
        else:
            raise ValueError(f"Unknown model: {model_name}")
    async def _call_lm(self, prompt: str) -> str:
        model = self.current_model if self.current_model else ("deepseek_v3" if self.tier in ["pro","enterprise"] else "deepseek_v2_lite")
        try:
            return await self.model_router.generate(prompt, model_name=model, max_tokens=512)
        except Exception as e:
            log.error(f"LLM call failed: {e}")
            return f"[Error: {e}]"
    def answer(self, user_input: str, language_model: str = None) -> Dict:
        start = time.time()
        active = self.modules.get_active()
        prompt = self.modules.apply_preprocessing(f"User: {user_input}\nAssistant:", user_input)
        if language_model:
            self.set_model(language_model)
        lm_output = asyncio.run(self._call_lm(prompt))
        final = self.modules.apply_postprocessing(lm_output)
        latency_ms = int((time.time() - start) * 1000)
        conv_id = self.memory.store(user_input, final, self.tier, active, self.current_model or "default", latency_ms)
        ts = datetime.datetime.utcnow().isoformat()
        self.vector_memory.add_text(user_input, conv_id, ts, {"role": "user"})
        self.vector_memory.add_text(final, conv_id, ts, {"role": "assistant", "modules": active})
        return {
            "answer": final,
            "modules_active": active,
            "conversation_id": conv_id,
            "latency_ms": latency_ms,
            "tier": self.tier
        }
    def answer_sync(self, user_input: str) -> str:
        return self.answer(user_input)["answer"]
    def recall_similar(self, query: str, limit: int = 5) -> List[Dict]:
        return self.vector_memory.search(query, limit)

def create_core(config_path="config/crownstar_config.json") -> "CrownStarCore":
    return CrownStarCore(config_path)

if __name__ == "__main__":
    core = create_core()
    print(core.answer_sync("Hello, CrownStar!"))

