# model_router_enhanced.py – Full router with registry and dynamic adapter loading
import asyncio
from typing import Optional, Dict, Any
from .base_adapter import LanguageModelAdapter
from .adapters.deepseek_adapter import DeepSeekAdapter
from .adapters.openai_adapter import OpenAIAdapter
from .adapters.claude_adapter import ClaudeAdapter
from .adapters.gemini_adapter import GeminiAdapter
from .adapters.llama_adapter import LlamaAdapter
from .adapters.chinese_adapters import (
    WenxinAdapter, TongyiAdapter, HunyuanAdapter, GLM4Adapter,
    MiniMaxAdapter, SparkAdapter, BaichuanAdapter, StepfunAdapter,
    SenseChatAdapter, TiangongAdapter, ZhinaoAdapter
)
from .model_registry import ModelRegistry

class EnhancedModelRouter:
    def __init__(self, default_model: str = "deepseek_v2_lite"):
        self.registry = ModelRegistry()
        self.adapters: Dict[str, LanguageModelAdapter] = {}
        self.default = default_model
        self._register_adapters()
    
    def _register_adapters(self):
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
        
        # Mistral
        self.adapters["mistral_large"] = self._create_mistral_adapter("Mistral-large-latest")
        self.adapters["mistral_medium"] = self._create_mistral_adapter("Mistral-medium-latest")
        self.adapters["mistral_small"] = self._create_mistral_adapter("Mistral-small-latest")
        
        # Cohere
        self.adapters["cohere_command_r"] = self._create_cohere_adapter("command-r-plus")
        self.adapters["cohere_command"] = self._create_cohere_adapter("command")
        
        # AI21
        self.adapters["ai21_j2_ultra"] = self._create_ai21_adapter("j2-ultra")
        self.adapters["ai21_j2_mid"] = self._create_ai21_adapter("j2-mid")
        
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
    
    def _create_mistral_adapter(self, model_name: str):
        # Stub for Mistral
        from .base_adapter import LanguageModelAdapter
        class MistralStub(LanguageModelAdapter):
            async def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
                return f"[Mistral {model_name}] {prompt[:100]}..."
            def get_model_info(self) -> dict:
                return {"name": model_name, "provider": "Mistral"}
        return MistralStub()
    
    def _create_cohere_adapter(self, model_name: str):
        from .base_adapter import LanguageModelAdapter
        class CohereStub(LanguageModelAdapter):
            async def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
                return f"[Cohere {model_name}] {prompt[:100]}..."
            def get_model_info(self) -> dict:
                return {"name": model_name, "provider": "Cohere"}
        return CohereStub()
    
    def _create_ai21_adapter(self, model_name: str):
        from .base_adapter import LanguageModelAdapter
        class AI21Stub(LanguageModelAdapter):
            async def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
                return f"[AI21 {model_name}] {prompt[:100]}..."
            def get_model_info(self) -> dict:
                return {"name": model_name, "provider": "AI21"}
        return AI21Stub()
    
    async def generate(self, prompt: str, model_name: Optional[str] = None, **kwargs) -> str:
        model = model_name or self.default
        # Validate tier compatibility
        info = self.registry.get_model(model)
        # (tier check would happen in core)
        adapter = self.adapters.get(model)
        if not adapter:
            raise ValueError(f"Unknown or unsupported model: {model}")
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
