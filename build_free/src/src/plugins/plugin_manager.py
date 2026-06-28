# src/plugins/plugin_manager.py – Full PluginManager with hooks, discovery, enable/disable
import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
import logging

logger = logging.getLogger(__name__)

class CrownStarPlugin:
    def __init__(self, core, info):
        self.core = core
        self.info = info
        self.logger = logging.getLogger(f"plugin.{info.name}")

    async def pre_answer(self, query: str, tier: str) -> Optional[str]:
        return None
    async def post_answer(self, query: str, response: str, tier: str) -> str:
        return response
    def on_startup(self): pass
    def on_shutdown(self): pass

class PluginManager:
    def __init__(self, core, plugin_dirs: List[Path] = None):
        self.core = core
        self.plugin_dirs = plugin_dirs or [Path("plugins")]
        self.plugins = {}
        self._enabled_plugins = set()
        self._hook_handlers = {"pre_answer": [], "post_answer": [], "startup": [], "shutdown": []}
        self._discover_plugins()
        self._load_enabled_plugins()

    def _discover_plugins(self):
        for plugin_dir in self.plugin_dirs:
            if not plugin_dir.exists():
                continue
            for py_file in plugin_dir.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue
                spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, CrownStarPlugin) and obj != CrownStarPlugin:
                        info = type('PluginInfo', (), {'name': py_file.stem, 'version': '0.1', 'author': 'unknown'})
                        self.plugins[py_file.stem] = {"class": obj, "info": info, "enabled": False}

    def _load_enabled_plugins(self):
        for name, data in self.plugins.items():
            if data["enabled"]:
                self.enable_plugin(name)

    def enable_plugin(self, name: str) -> bool:
        if name not in self.plugins:
            return False
        data = self.plugins[name]
        if data["enabled"]:
            return True
        try:
            instance = data["class"](self.core, data["info"])
            instance.on_startup()
            self._hook_handlers["pre_answer"].append(instance.pre_answer)
            self._hook_handlers["post_answer"].append(instance.post_answer)
            data["instance"] = instance
            data["enabled"] = True
            self._enabled_plugins.add(name)
            return True
        except Exception as e:
            logger.error(f"Failed to enable plugin {name}: {e}")
            return False

    def run_startup_hooks(self):
        for handler in self._hook_handlers["startup"]:
            try:
                handler()
            except Exception as e:
                logger.error(f"Startup hook failed: {e}")

    def run_shutdown_hooks(self):
        for handler in self._hook_handlers["shutdown"]:
            try:
                handler()
            except Exception as e:
                logger.error(f"Shutdown hook failed: {e}")

    async def run_post_answer_hooks(self, query: str, response: str, tier: str) -> str:
        current = response
        for handler in self._hook_handlers["post_answer"]:
            try:
                current = await handler(query, current, tier)
            except Exception as e:
                logger.error(f"Post‑answer hook failed: {e}")
        return current
