# crownstar_cli_advanced.py – Enhanced CLI with persistent sessions
import sys, os, readline, atexit, json, time
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))
from crownstar_core import create_core

HISTORY_FILE = Path.home() / ".crownstar_history"
SESSION_FILE = Path.home() / ".crownstar_session.json"

class CrownStarCLI:
    def __init__(self):
        self.core = create_core()
        self.running = True
        self._setup_readline()
        self._load_session()
        self.commands = {
            "/help": self.cmd_help, "/quit": self.cmd_quit, "/exit": self.cmd_quit,
            "/toggle": self.cmd_toggle, "/modules": self.cmd_modules, "/history": self.cmd_history,
            "/recall": self.cmd_recall, "/save": self.cmd_save, "/load": self.cmd_load,
            "/clear": self.cmd_clear, "/model": self.cmd_model, "/tier": self.cmd_tier,
            "/search": self.cmd_search, "/stats": self.cmd_stats
        }
    def _setup_readline(self):
        readline.set_history_length(2000)
        if HISTORY_FILE.exists():
            readline.read_history_file(str(HISTORY_FILE))
        atexit.register(lambda: readline.write_history_file(str(HISTORY_FILE)))
        completions = list(self.commands.keys()) + ["on", "off"] + self.core.model_router.list_models()
        def completer(text, state):
            options = [c for c in completions if c.startswith(text)]
            return options[state] if state < len(options) else None
        readline.set_completer(completer)
        readline.parse_and_bind("tab: complete")
    def _load_session(self):
        if SESSION_FILE.exists():
            try:
                with open(SESSION_FILE, 'r') as f:
                    data = json.load(f)
                    for mod, state in data.get("modules", {}).items():
                        self.core.set_module(mod, state)
                    if "tier" in data:
                        self.core.set_tier(data["tier"])
                    if "model" in data:
                        self.core.set_model(data["model"])
                    print(f"Session loaded: {len(data.get('modules', {}))} modules restored")
            except Exception as e:
                print(f"Session load error: {e}")
    def _save_session(self):
        data = {
            "modules": self.core.modules.modules_state,
            "tier": self.core.tier,
            "model": self.core.current_model,
            "timestamp": time.time()
        }
        with open(SESSION_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    def cmd_help(self, args):  # (shortened for brevity – full version exists in original)
        print("\nCrownStar v7.0.1 Commands:")
        for cmd in sorted(self.commands.keys()):
            print(f"  {cmd}")
    def cmd_quit(self, args): self._save_session(); self.running = False
    def cmd_toggle(self, args):
        parts = args.strip().split()
        if len(parts) != 2:
            print("Usage: /toggle <module> on|off")
            return
        mod, state = parts
        self.core.set_module(mod, state.lower() == "on")
        self._save_session()
    def cmd_modules(self, args):
        for k, v in self.core.modules.modules_state.items():
            print(f"{k:30} {'ON' if v else 'OFF'}")
    def cmd_history(self, args):
        history = self.core.memory.get_full_history(limit=20)
        if not history: print("No conversation history yet."); return
        for h in reversed(history[-10:]):
            print(f"[{h['timestamp']}] U: {h['user'][:60]}\n            A: {h['assistant'][:60]}\n")
    def cmd_recall(self, args):
        if not args.strip(): print("Usage: /recall <search text>"); return
        results = self.core.vector_memory.search(args.strip(), limit=5)
        for r in results:
            print(f"[{r['timestamp']}] Score: {r['score']:.2f}\n  {r['text'][:200]}\n")
    def cmd_search(self, args):
        if not args.strip(): print("Usage: /search <query>"); return
        results = self.core.vector_memory.search(args.strip(), k=10)
        for r in results:
            print(f"[{r['timestamp']}] Score: {r['score']:.3f}\n  {r['text'][:150]}...\n")
    def cmd_save(self, args): self._save_session(); print("Session saved.")
    def cmd_load(self, args): self._load_session(); print("Session reloaded.")
    def cmd_clear(self, args): os.system('cls' if os.name == 'nt' else 'clear'); self._print_banner()
    def cmd_model(self, args):
        if args.strip():
            try:
                self.core.set_model(args.strip()); self._save_session()
                print(f"Model switched to {args.strip()}")
            except ValueError as e: print(e)
        else:
            print("Available models:", self.core.model_router.list_models())
            print(f"Current model: {self.core.current_model or 'default'}")
    def cmd_tier(self, args):
        if args.strip():
            try: self.core.set_tier(args.strip()); self._save_session()
            except ValueError as e: print(e)
        print(f"Current tier: {self.core.tier}")
    def cmd_stats(self, args):
        print(f"CrownStar v{self.core.config['version']}\nTier: {self.core.tier}\nModel: {self.core.current_model or 'auto'}")
        print(f"Hardware: {self.core.hardware.cpu_count} cores, {self.core.hardware.total_ram_gb:.1f}GB RAM")
        print(f"GPU: {self.core.hardware.gpu_name if self.core.hardware.has_gpu else 'None'}")
        active = self.core.modules.get_active()
        print(f"Active modules: {len(active)} -> {active if active else 'None'}")
    def _print_banner(self):
        print("\033[95m" + "="*60)
        print(f" CrownStar v{self.core.config['version']} – Sovereign AI CLI (Advanced)")
        print(" Type /help for commands. Tab completion enabled.")
        print("="*60 + "\033[0m")
        active = self.core.modules.get_active()
        print(f"Active modules: {active if active else 'None'}")
        print(f"Current tier: {self.core.tier} | Model: {self.core.current_model or 'auto'}")
    def run(self):
        self._print_banner()
        while self.running:
            try:
                inp = input("\033[92m> \033[0m").strip()
                if not inp: continue
                if inp.startswith('/'):
                    parts = inp.split(maxsplit=1)
                    cmd = parts[0].lower()
                    arg = parts[1] if len(parts) > 1 else ""
                    if cmd in self.commands:
                        self.commands[cmd](arg)
                    else:
                        print(f"Unknown command: {cmd}")
                else:
                    print("\033[96mThinking...\033[0m")
                    resp = self.core.answer_sync(inp)
                    print(f"\033[93mCrownStar:\033[0m {resp}\n")
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"\033[91mError: {e}\033[0m")

if __name__ == "__main__":
    cli = CrownStarCLI()
    cli.run()
