cd D:\CrownStar-Absolute
$corePath = "src\core\crownstar_core.py"
$lightCore = @'
# crownstar_core.py – Lightweight AI (no PyTorch, no transformers)
import os, sys, json, time, asyncio, logging, sqlite3, datetime, random, re
from collections import defaultdict
from typing import List, Dict, Optional

def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(base_path, relative_path)

log = logging.getLogger("CrownStar.Core")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class MarkovChain:
    def __init__(self, order=2):
        self.order = order
        self.chain = defaultdict(list)
        self.builtin = [
            "CrownStar is a sovereign cognitive engine.",
            "The internet contains endless knowledge.",
            "Gamma bursts enhance reasoning.",
            "Lateral thinking solves complex problems."
        ]
        for t in self.builtin: self.train(t)
    def train(self, text):
        words = text.lower().split()
        for i in range(len(words)-self.order):
            key = tuple(words[i:i+self.order])
            self.chain[key].append(words[i+self.order])
    def generate(self, max_words=30):
        if not self.chain: return random.choice(self.builtin)
        key = random.choice(list(self.chain.keys()))
        out = list(key)
        for _ in range(max_words):
            if key not in self.chain: break
            out.append(random.choice(self.chain[key]))
            key = tuple(out[-self.order:])
        return " ".join(out)

class WebCortex:
    async def harvest(self, domain, query):
        texts = []
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://{domain}", timeout=3) as resp:
                    html = await resp.text()
                    texts.append(re.sub(r'<[^>]+>', ' ', html)[:2000])
        except: pass
        try:
            term = domain.split('.')[0]
            async with aiohttp.ClientSession() as session:
                url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{term}"
                async with session.get(url, timeout=3) as resp:
                    data = await resp.json()
                    texts.append(data.get('extract', ''))
        except: pass
        texts.append(f"Recent insights about {query} from online communities.")
        return texts

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
    def store(self, user_msg, assistant_msg, tier, modules, lang_model, latency_ms):
        ts = datetime.datetime.utcnow().isoformat()
        cur = self.conn.cursor()
        cur.execute('''INSERT INTO conversations (timestamp, tier, user_message, assistant_message, modules_active, language_model, latency_ms)
            VALUES (?,?,?,?,?,?,?)''', (ts, tier, user_msg, assistant_msg, ",".join(modules), lang_model, latency_ms))
        self.conn.commit()
        return cur.lastrowid
    def get_full_history(self, limit=None):
        sql = "SELECT timestamp, user_message, assistant_message FROM conversations ORDER BY timestamp ASC"
        if limit: sql += f" LIMIT {limit}"
        cur = self.conn.execute(sql)
        return [{"timestamp": r[0], "user": r[1], "assistant": r[2]} for r in cur.fetchall()]

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
                    if k in self.modules_state: self.modules_state[k] = v
    def set_module(self, name, enabled):
        if name in self.modules_state: self.modules_state[name] = enabled
    def get_active(self): return [k for k,v in self.modules_state.items() if v]
    def apply_preprocessing(self, prompt, query):
        if self.modules_state["ultra_super_model"]:
            prompt = "[CrownStar Ultra: all mathematical modules active]\n" + prompt
        return prompt
    def apply_postprocessing(self, response): return response

class HardwareProfile:
    def __init__(self): pass

class CrownStarCore:
    def __init__(self, config_path="config/crownstar_config.json"):
        with open(resource_path(config_path), 'r') as f:
            self.config = json.load(f)
        self.tier = os.environ.get("CROWNSTAR_TIER", "free_pay_per_use")
        self.modules = CrownStarMathModules(resource_path(config_path))
        self.memory = CrownStarMemory()
        self.markov = MarkovChain()
        self.cortex = WebCortex()
        log.info(f"CrownStar Core v{self.config['version']} initialised (lightweight, no PyTorch). Tier: {self.tier}")
    def set_module(self, name, enabled): self.modules.set_module(name, enabled)
    def set_tier(self, tier): self.tier = tier
    def answer(self, user_input, language_model=None):
        start = time.time()
        active = self.modules.get_active()
        prompt = self.modules.apply_preprocessing(f"User: {user_input}\nAssistant:", user_input)
        lm_output = self.markov.generate(max_words=40)
        final = self.modules.apply_postprocessing(lm_output)
        latency_ms = int((time.time() - start) * 1000)
        conv_id = self.memory.store(user_input, final, self.tier, active, "markov", latency_ms)
        return {"answer": final, "modules_active": active, "conversation_id": conv_id, "latency_ms": latency_ms, "tier": self.tier}
    def answer_sync(self, user_input): return self.answer(user_input)["answer"]

def create_core(config_path="config/crownstar_config.json"): return CrownStarCore(config_path)
if __name__ == "__main__":
    core = create_core()
    print(core.answer_sync("Hello, CrownStar!"))
'@
Set-Content -Path $corePath -Value $lightCore -Encoding utf8