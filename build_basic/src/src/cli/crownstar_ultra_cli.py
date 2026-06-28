# crownstar_ultra_cli.py – Ultra-advanced CLI with history persistence, macros, batch mode
import sys
import os
import json
import readline
import atexit
import time
import argparse
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))
from crownstar_core import create_core

# Constants
HISTORY_FILE = Path.home() / ".crownstar_history"
SESSION_FILE = Path.home() / ".crownstar_session.json"
MACRO_FILE = Path.home() / ".crownstar_macros.json"
ENV_FILE = Path.cwd() / ".env"

class CrownStarUltraCLI:
    def __init__(self, batch_mode: bool = False, batch_file: str = None):
        self.core = create_core()
        self.running = True
        self.batch_mode = batch_mode
        self.batch_file = batch_file
        self.macros = self._load_macros()
        self.aliases = {
            "q": "/quit", "exit": "/quit", "h": "/help", "m": "/modules",
            "t": "/tier", "mod": "/model", "hist": "/history", "rec": "/recall"
        }
        self._setup_readline()
        self._load_env()
        self._load_session()
    
    def _setup_readline(self):
        try:
            readline.set_history_length(5000)
            if HISTORY_FILE.exists():
                readline.read_history_file(str(HISTORY_FILE))
            atexit.register(lambda: readline.write_history_file(str(HISTORY_FILE)))
            # Auto-completion for commands and modules
            completions = ["/help", "/quit", "/exit", "/toggle", "/modules", "/history",
                          "/recall", "/save", "/load", "/clear", "/model", "/tier",
                          "/stats", "/macro", "/alias", "/batch", "/env", "/time",
                          "on", "off"] + list(self.core.modules.modules_state.keys())
            def completer(text, state):
                options = [c for c in completions if c.startswith(text)]
                return options[state] if state < len(options) else None
            readline.set_completer(completer)
            readline.parse_and_bind("tab: complete")
        except Exception:
            pass
    
    def _load_env(self):
        """Load environment variables from .env file"""
        if ENV_FILE.exists():
            with open(ENV_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, val = line.split('=', 1)
                        os.environ[key] = val
            print(f"Loaded environment from {ENV_FILE}")
    
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
                    print(f"Session restored (modules: {len(data.get('modules', {}))})")
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
    
    def _load_macros(self):
        if MACRO_FILE.exists():
            with open(MACRO_FILE, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_macros(self):
        with open(MACRO_FILE, 'w') as f:
            json.dump(self.macros, f, indent=2)
    
    def _print_banner(self):
        print("\033[95m" + "="*70)
        print(f" CrownStar v{self.core.config['version']} – Ultra CLI")
        print(" Tab completion | Command history | Macros | Batch mode | Streaming ready")
        print("="*70 + "\033[0m")
        active = self.core.modules.get_active()
        print(f"Active modules: {len(active)} – {', '.join(active) if active else 'None'}")
        print(f"Tier: {self.core.tier} | Model: {self.core.current_model or 'auto'}")
        print("Type /help for commands, /macro save <name> to create macro\n")
    
    def cmd_help(self, args):
        help_text = """
╔══════════════════════════════════════════════════════════════════╗
║ CrownStar Ultra CLI Commands                                     ║
╠══════════════════════════════════════════════════════════════════╣
║ /help                    – Show this help                        ║
║ /quit, /exit             – Exit CLI                              ║
║ /toggle <module> on|off  – Enable/disable math module            ║
║ /modules                 – List all modules and status           ║
║ /history                 – Show recent conversation history      ║
║ /recall <query>          – Semantic search past conversations    ║
║ /save                    – Save current session                  ║
║ /load                    – Reload saved session                  ║
║ /clear                   – Clear screen                          ║
║ /model [name]            – Show/switch language model            ║
║ /tier [name]             – Show/switch tier                      ║
║ /stats                   – Show system statistics                ║
║ /macro list              – List all macros                       ║
║ /macro save <name>       – Save current input as macro           ║
║ /macro run <name>        – Execute macro                         ║
║ /macro delete <name>     – Delete macro                          ║
║ /alias list              – List aliases                          ║
║ /alias add <short> <cmd> – Add alias                             ║
║ /batch <file>            – Run commands from file                ║
║ /env                      – Show environment variables           ║
║ /time                     – Show current time and uptime         ║
╚══════════════════════════════════════════════════════════════════╝
"""
        print(help_text)
    
    def cmd_quit(self, args):
        self._save_session()
        self.running = False
    
    def cmd_toggle(self, args):
        parts = args.strip().split()
        if len(parts) != 2:
            print("Usage: /toggle <module> on|off")
            return
        mod, state = parts
        self.core.set_module(mod, state.lower() == "on")
        self._save_session()
        print(f"Module {mod} turned {state.upper()}")
    
    def cmd_modules(self, args):
        print(f"\n{'Module':30} {'Status':8} {'Description'}")
        print("-" * 70)
        desc = {
            "base_3layer_jacobian": "Jacobian sensitivity",
            "hessian_backprop": "Second-order opt",
            "universal_approx": "UAT guarantee",
            "gurney_3stage": "Three-stage neuron",
            "yegnanarayana_tensor": "Tensor composition",
            "haykin_recursive": "Recursive layers",
            "bishop_probabilistic": "Probabilistic view",
            "zurada_indexed": "Indexed notation",
            "ultra_super_model": "Ultra-super model"
        }
        for k, v in self.core.modules.modules_state.items():
            status = "ON" if v else "OFF"
            d = desc.get(k, k.replace('_', ' '))
            print(f"{k:30} {status:8} {d}")
        print()
    
    def cmd_history(self, args):
        limit = 15
        history = self.core.memory.get_full_history(limit=limit)
        if not history:
            print("No conversation history.")
            return
        print(f"\nRecent {len(history)} conversations:")
        for i, h in enumerate(reversed(history)):
            print(f"\n[{i+1}] {h['timestamp']}")
            print(f"  U: {h['user'][:80]}")
            print(f"  A: {h['assistant'][:80]}")
    
    def cmd_recall(self, args):
        query = args.strip()
        if not query:
            print("Usage: /recall <search text>")
            return
        results = self.core.vector_memory.search(query, k=5)
        if not results:
            print("No matching memories found.")
            return
        print(f"\nSearch results for '{query}':")
        for r in results:
            print(f"\n[Score: {r['score']:.3f}] {r['timestamp']}")
            print(f"  {r['text'][:200]}...")
    
    def cmd_save(self, args):
        self._save_session()
        print("Session saved.")
    
    def cmd_load(self, args):
        self._load_session()
        print("Session reloaded.")
    
    def cmd_clear(self, args):
        os.system('cls' if os.name == 'nt' else 'clear')
        self._print_banner()
    
    def cmd_model(self, args):
        if args.strip():
            try:
                self.core.set_model(args.strip())
                self._save_session()
                print(f"Model switched to {args.strip()}")
            except ValueError as e:
                print(e)
        else:
            print(f"Current model: {self.core.current_model or 'auto'}")
            print("Available models:", ", ".join(self.core.model_router.list_models()[:10]), "...")
    
    def cmd_tier(self, args):
        if args.strip():
            try:
                self.core.set_tier(args.strip())
                self._save_session()
                print(f"Tier switched to {args.strip()}")
            except ValueError as e:
                print(e)
        else:
            print(f"Current tier: {self.core.tier}")
    
    def cmd_stats(self, args):
        print(f"\nCrownStar v{self.core.config['version']}")
        print(f"Tier: {self.core.tier}")
        print(f"Model: {self.core.current_model or 'auto'}")
        print(f"Hardware: {self.core.hardware.cpu_count} cores, {self.core.hardware.total_ram_gb:.1f}GB RAM")
        print(f"GPU: {self.core.hardware.gpu_name if self.core.hardware.has_gpu else 'None'}")
        active = self.core.modules.get_active()
        print(f"Active modules: {len(active)}")
        print(f"Memory: {self.core.vector_memory.index.ntotal} vectors indexed")
        print(f"Uptime: {time.time() - self.core.start_time if hasattr(self.core, 'start_time') else 'N/A'}s")
    
    def cmd_macro(self, args):
        parts = args.strip().split()
        if not parts:
            print("Usage: /macro list|save <name>|run <name>|delete <name>")
            return
        sub = parts[0]
        if sub == "list":
            if not self.macros:
                print("No macros defined.")
            else:
                print("Macros:")
                for name, cmd in self.macros.items():
                    print(f"  {name}: {cmd}")
        elif sub == "save" and len(parts) == 2:
            name = parts[1]
            # Capture last input from readline history
            # For simplicity, ask user
            cmd = input(f"Enter command for macro '{name}': ").strip()
            self.macros[name] = cmd
            self._save_macros()
            print(f"Macro '{name}' saved.")
        elif sub == "run" and len(parts) == 2:
            name = parts[1]
            if name in self.macros:
                self.execute_command(self.macros[name])
            else:
                print(f"Macro '{name}' not found.")
        elif sub == "delete" and len(parts) == 2:
            name = parts[1]
            if name in self.macros:
                del self.macros[name]
                self._save_macros()
                print(f"Macro '{name}' deleted.")
            else:
                print(f"Macro '{name}' not found.")
        else:
            print("Invalid macro command")
    
    def cmd_alias(self, args):
        parts = args.strip().split()
        if not parts:
            print("Aliases:", self.aliases)
            return
        if parts[0] == "list":
            for k, v in self.aliases.items():
                print(f"  {k} -> {v}")
        elif parts[0] == "add" and len(parts) >= 3:
            alias = parts[1]
            cmd = " ".join(parts[2:])
            self.aliases[alias] = cmd
            print(f"Alias '{alias}' added -> {cmd}")
        elif parts[0] == "remove" and len(parts) == 2:
            alias = parts[1]
            if alias in self.aliases:
                del self.aliases[alias]
                print(f"Alias '{alias}' removed.")
            else:
                print(f"Alias '{alias}' not found.")
        else:
            print("Usage: /alias list|add <short> <cmd>|remove <short>")
    
    def cmd_batch(self, args):
        filepath = args.strip()
        if not filepath:
            print("Usage: /batch <filename>")
            return
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            return
        with open(filepath, 'r') as f:
            lines = f.readlines()
        print(f"Running batch from {filepath} ({len(lines)} lines)")
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                print(f"\n> {line}")
                self.execute_command(line)
    
    def cmd_env(self, args):
        print("Environment variables:")
        for k, v in os.environ.items():
            if any(x in k.lower() for x in ["key", "token", "secret", "api"]):
                v = v[:4] + "..." if len(v) > 8 else "***"
            print(f"  {k}={v}")
    
    def cmd_time(self, args):
        now = datetime.now()
        print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        if hasattr(self.core, 'start_time'):
            uptime = time.time() - self.core.start_time
            print(f"Uptime: {int(uptime//3600)}h {int((uptime%3600)//60)}m {int(uptime%60)}s")
    
    def execute_command(self, cmd):
        if cmd.startswith('/'):
            parts = cmd.split(maxsplit=1)
            cmd_name = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            method_name = f"cmd_{cmd_name[1:]}"
            if hasattr(self, method_name):
                getattr(self, method_name)(args)
            else:
                print(f"Unknown command: {cmd_name}")
        else:
            # Regular chat
            print("\033[96mStreaming response (Ctrl+C to stop)...\033[0m")
            try:
                resp = self.core.answer_sync(cmd)
                print(f"\033[93mCrownStar:\033[0m {resp}\n")
            except KeyboardInterrupt:
                print("\nStream interrupted")
    
    def run(self):
        if self.batch_mode and self.batch_file:
            self.cmd_batch(self.batch_file)
            return
        
        self._print_banner()
        while self.running:
            try:
                inp = input("\033[92m> \033[0m").strip()
                if not inp:
                    continue
                # Expand alias
                if inp in self.aliases:
                    inp = self.aliases[inp]
                self.execute_command(inp)
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"\033[91mError: {e}\033[0m")
        self._save_session()

def main():
    parser = argparse.ArgumentParser(description="CrownStar Ultra CLI")
    parser.add_argument("--batch", "-b", help="Run batch commands from file")
    parser.add_argument("--query", "-q", help="Single query (non-interactive)")
    parser.add_argument("--json", action="store_true", help="Output JSON (with --query)")
    args = parser.parse_args()
    
    cli = CrownStarUltraCLI(batch_mode=bool(args.batch), batch_file=args.batch)
    
    if args.query:
        if args.json:
            result = cli.core.answer(args.query)
            print(json.dumps(result, indent=2))
        else:
            resp = cli.core.answer_sync(args.query)
            print(resp)
    else:
        cli.run()

if __name__ == "__main__":
    main()
