# chinese_adapters_extended.py – Additional Chinese model adapters
from .base_adapter import LanguageModelAdapter

class SenseChatAdapter(LanguageModelAdapter):
    async def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        # SenseChat 5 by SenseTime
        return f"[SenseChat 5] {prompt[:100]}..."
    def get_model_info(self) -> dict:
        return {"name": "SenseChat 5", "provider": "SenseTime"}

class TiangongAdapter(LanguageModelAdapter):
    async def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        # Tiangong by Kunlun
        return f"[天工] {prompt[:100]}..."
    def get_model_info(self) -> dict:
        return {"name": "天工", "provider": "Kunlun"}

class ZhinaoAdapter(LanguageModelAdapter):
    async def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        # 360 Zhinao
        return f"[360智脑] {prompt[:100]}..."
    def get_model_info(self) -> dict:
        return {"name": "360智脑", "provider": "Qihoo 360"}
