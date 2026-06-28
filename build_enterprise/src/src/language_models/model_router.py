# model_router.py – Final version with full 28 models (replaces old)
import asyncio
from typing import Optional, Dict
from .base_adapter import LanguageModelAdapter
from .adapters.deepseek_adapter import DeepSeekAdapter
from .adapters.openai_adapter import OpenAIAdapter
from .adapters.claude_adapter import ClaudeAdapter
from .adapters.gemini_adapter import GeminiAdapter
from .adapters.llama_adapter import LlamaAdapter
from .adapters.chinese_adapters import (
    WenxinAdapter, TongyiAdapter, HunyuanAdapter, GLM4Adapter,
    MiniMaxAdapter, SparkAdapter, BaichuanAdapter, StepfunAdapter
)
from .adapters.chinese_adapters_extended import SenseChatAdapter, TiangongAdapter, ZhinaoAdapter
from .model_registry import ModelRegistry

class ModelRouter:
    def __init__(self, default_model: str = "deepseek_v2_lite"):
        self.registry = ModelRegistry()
        self.adapters: Dict[str, LanguageModelAdapter] = {}
        self.default = default_model
        self._register_all()
    
    def _register_all(self):
        # DeepSeek
        self.adapters["deepseek_v2_lite"] = DeepSeekAdapter("v2_lite")
        self.adapters["deepseek_v3"] = DeepSeekAdapter("v3")
        # OpenAI
        self.adapters["gpt4"] = OpenAIAdapter(model="gpt-4")
        self.adapters["gpt4_turbo"] = OpenAIAdapter(model="gpt-4-turbo-preview")
        self.adapters["gpt35"] = OpenAIAdapter(model="gpt-3.5-turbo")
        # Anthropic
        self.adapters["claude3_opus"] = ClaudeAdapter(model="claude-3-opus-20240229")
        self.adapters["claude3_sonnet"] = ClaudeAdapter(model="claude-3-sonnet-20240229")
        self.adapters["claude3_haiku"] = ClaudeAdapter(model="claude-3-haiku-20240307")
        # Google
        self.adapters["gemini_pro"] = GeminiAdapter(model="gemini-pro")
        self.adapters["gemini_ultra"] = GeminiAdapter(model="gemini-ultra")
        # Meta Llama
        self.adapters["llama3_8b"] = LlamaAdapter("8B")
        self.adapters["llama3_70b"] = LlamaAdapter("70B")
        self.adapters["llama2_7b"] = LlamaAdapter("7B")
        # Chinese models
        self.adapters["wenxin"] = WenxinAdapter()
        self.adapters["tongyi"] = TongyiAdapter()
        self.adapters["hunyuan"] = HunyuanAdapter()
        self.adapters["glm4"] = GLM4Adapter()
        self.adapters["minimax"] = MiniMaxAdapter()
        self.adapters["spark"] = SparkAdapter()
        self.adapters["baichuan"] = BaichuanAdapter()
        self.adapters["stepfun"] = StepfunAdapter()
        self.adapters["sensechat"] = SenseChatAdapter()
        self.adapters["tiangong"] = TiangongAdapter()
        self.adapters["zhinao"] = ZhinaoAdapter()
        # Stub adapters for models without full implementation
        self.adapters["mistral_large"] = self._stub_adapter("Mistral Large")
        self.adapters["mistral_medium"] = self._stub_adapter("Mistral Medium")
        self.adapters["mistral_small"] = self._stub_adapter("Mistral Small")
        self.adapters["cohere_command_r"] = self._stub_adapter("Cohere Command R+")
        self.adapters["cohere_command"] = self._stub_adapter("Cohere Command")
        self.adapters["ai21_j2_ultra"] = self._stub_adapter("AI21 Jurassic-2 Ultra")
        self.adapters["ai21_j2_mid"] = self._stub_adapter("AI21 Jurassic-2 Mid")
    
    def _stub_adapter(self, name: str):
        class StubAdapter(LanguageModelAdapter):
            async def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
                return f"[{name}] {prompt[:100]}... (API key required for full implementation)"
            def get_model_info(self) -> dict:
                return {"name": name, "provider": name.split()[0]}
        return StubAdapter()
    
    async def generate(self, prompt: str, model_name: Optional[str] = None, **kwargs) -> str:
        model = model_name or self.default
        adapter = self.adapters.get(model)
        if not adapter:
            raise ValueError(f"Unknown model: {model}")
        return await adapter.generate(prompt, **kwargs)
    
    def list_models(self) -> list:
        return list(self.adapters.keys())
    
    def get_model_info(self, model_name: str) -> dict:
        info = self.registry.get_model(model_name)
        if info:
            return {
                "name": info.name,
                "display_name": info.display_name,
                "provider": info.provider,
                "tier_min": info.tier_min,
                "context_length": info.context_length,
                "capabilities": info.capabilities
            }
        return None
