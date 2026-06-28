# crownstar_desktop.py – Portable version
import sys
import os
import webview

# Add the src directory to module search path
if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(base_dir, '..')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

try:
    from src.core.crownstar_core import create_core
except ImportError:
    from crownstar_core import create_core

core = create_core()

class CrownStarAPI:
    def chat(self, message: str) -> str:
        return core.answer_sync(message)
    def toggle_module(self, module: str, enabled: bool) -> str:
        core.set_module(module, enabled)
        return f"Module {module} {'enabled' if enabled else 'disabled'}"
    def get_modules(self) -> dict:
        return core.modules.modules_state
    def set_tier(self, tier: str) -> str:
        core.set_tier(tier)
        return f"Tier set to {tier}"
    def get_tier(self) -> str:
        return core.tier
    def set_model(self, model: str) -> str:
        core.set_model(model)
        return f"Model set to {model}"
    def list_models(self) -> list:
        return core.model_router.list_models()

def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

html_path = resource_path("src/ui/index.html")
if not os.path.exists(html_path):
    html_path = os.path.join(os.path.dirname(__file__), "index.html")

with open(html_path, 'r', encoding='utf-8') as f:
    html_content = f.read()

def main():
    webview.create_window("CrownStar v7.1.0 – Regal Futurism", html=html_content, js_api=CrownStarAPI(), width=1300, height=800)
    webview.start()

if __name__ == "__main__":
    main()
