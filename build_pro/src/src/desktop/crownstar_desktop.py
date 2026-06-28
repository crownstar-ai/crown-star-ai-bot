# Fixed crownstar_desktop.py for pywebview 6.2+ and dataloader import
import sys, os, asyncio, threading, json, logging, webview, traceback
sys.path.insert(0, os.path.dirname(__file__) + "/..")
from core.crownstar_core import CrownStarCore
from core.dataloader import create_streaming_dataloader as create_dataloader   # alias

class CrownStarDesktopApp:
    def __init__(self):
        self.core = None
        self.window = None
        self.settings = {"tier":"free","temperature":0.85,"min_len":32,"max_len":512,"mode":"regal_futurism"}
        self.logger = logging.getLogger("CrownStar.Desktop")

    def init_core(self):
        try:
            self.core = CrownStarCore(lazy_load=True)
            self.core.ensure_model()
            self.logger.info("Core loaded")
        except Exception as e:
            self.logger.error(f"Failed to init core: {e}")
            traceback.print_exc()

    def run(self):
        self.window = webview.create_window(
            "CrownStar‑Absolute",
            "src/ui/index.html",
            js_api=CrownStarJsApi(self),
            width=1200, height=800
        )
        webview.start(self._on_started, self.window)

    def _on_started(self):
        self.init_core()

    def _create_menu(self):
        # Pywebview 6 uses a list of dicts/tuples for menus
        return [
            ("File", [
                ("New Conversation", self._new_conversation),
                ("Export Conversation", self._export_conversation),
                ("Quit", self.window.destroy)
            ]),
            ("View", [
                ("Settings", self._open_settings)
            ])
        ]

    def _new_conversation(self): pass
    def _export_conversation(self): pass
    def _open_settings(self): pass

class CrownStarJsApi:
    def __init__(self, app): self.app = app
    def send_message(self, msg, tier="free", temperature=0.85, min_length=32, max_length=512, mode="regal_futurism"):
        if not self.app.core: return "Core not ready"
        loop = asyncio.new_event_loop()
        try:
            resp = loop.run_until_complete(
                self.app.core.answer(msg, tier=tier, temperature=temperature,
                                     min_length=min_length, max_length=max_length, mode=mode)
            )
            return resp
        except Exception as e:
            return f"Error: {e}"
        finally:
            loop.close()

if __name__ == "__main__":
    app = CrownStarDesktopApp()
    app.run()

