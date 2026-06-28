# model_registry.py – Central registry of all supported language models
from typing import Dict, Optional, List, Any
from dataclasses import dataclass

@dataclass
class ModelInfo:
    name: str
    display_name: str
    provider: str
    tier_min: str  # minimum subscription tier: "free", "basic", "pro", "enterprise"
    context_length: int
    capabilities: List[str]  # "chat", "completion", "json", "vision", "tools"
    requires_api_key: bool
    api_key_env: Optional[str] = None

class ModelRegistry:
    _instance = None
    _models: Dict[str, ModelInfo] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._register_all_models()
        return cls._instance
    
    def _register_all_models(self):
        # DeepSeek
        self._models["deepseek_v2_lite"] = ModelInfo(
            name="deepseek_v2_lite", display_name="DeepSeek V2 Lite", provider="DeepSeek",
            tier_min="free", context_length=4096, capabilities=["chat", "completion"], requires_api_key=False
        )
        self._models["deepseek_v3"] = ModelInfo(
            name="deepseek_v3", display_name="DeepSeek V3", provider="DeepSeek",
            tier_min="pro", context_length=8192, capabilities=["chat", "completion"], requires_api_key=False
        )
        
        # OpenAI
        self._models["gpt4"] = ModelInfo(
            name="gpt4", display_name="GPT-4", provider="OpenAI",
            tier_min="basic", context_length=8192, capabilities=["chat", "completion", "json", "tools"], requires_api_key=True, api_key_env="OPENAI_API_KEY"
        )
        self._models["gpt4_turbo"] = ModelInfo(
            name="gpt4_turbo", display_name="GPT-4 Turbo", provider="OpenAI",
            tier_min="pro", context_length=128000, capabilities=["chat", "completion", "json", "tools", "vision"], requires_api_key=True, api_key_env="OPENAI_API_KEY"
        )
        self._models["gpt35"] = ModelInfo(
            name="gpt35", display_name="GPT-3.5 Turbo", provider="OpenAI",
            tier_min="free", context_length=16384, capabilities=["chat", "completion"], requires_api_key=True, api_key_env="OPENAI_API_KEY"
        )
        
        # Anthropic
        self._models["claude3_opus"] = ModelInfo(
            name="claude3_opus", display_name="Claude 3 Opus", provider="Anthropic",
            tier_min="pro", context_length=200000, capabilities=["chat", "completion", "json", "vision"], requires_api_key=True, api_key_env="ANTHROPIC_API_KEY"
        )
        self._models["claude3_sonnet"] = ModelInfo(
            name="claude3_sonnet", display_name="Claude 3 Sonnet", provider="Anthropic",
            tier_min="basic", context_length=200000, capabilities=["chat", "completion", "json"], requires_api_key=True, api_key_env="ANTHROPIC_API_KEY"
        )
        self._models["claude3_haiku"] = ModelInfo(
            name="claude3_haiku", display_name="Claude 3 Haiku", provider="Anthropic",
            tier_min="free", context_length=200000, capabilities=["chat", "completion"], requires_api_key=True, api_key_env="ANTHROPIC_API_KEY"
        )
        
        # Google
        self._models["gemini_pro"] = ModelInfo(
            name="gemini_pro", display_name="Gemini Pro", provider="Google",
            tier_min="basic", context_length=32768, capabilities=["chat", "completion", "json", "vision"], requires_api_key=True, api_key_env="GOOGLE_API_KEY"
        )
        self._models["gemini_ultra"] = ModelInfo(
            name="gemini_ultra", display_name="Gemini Ultra", provider="Google",
            tier_min="pro", context_length=32768, capabilities=["chat", "completion", "json", "vision", "tools"], requires_api_key=True, api_key_env="GOOGLE_API_KEY"
        )
        
        # Meta Llama
        self._models["llama3_8b"] = ModelInfo(
            name="llama3_8b", display_name="Llama 3 8B", provider="Meta",
            tier_min="free", context_length=8192, capabilities=["chat", "completion"], requires_api_key=False
        )
        self._models["llama3_70b"] = ModelInfo(
            name="llama3_70b", display_name="Llama 3 70B", provider="Meta",
            tier_min="basic", context_length=8192, capabilities=["chat", "completion"], requires_api_key=False
        )
        self._models["llama2_7b"] = ModelInfo(
            name="llama2_7b", display_name="Llama 2 7B", provider="Meta",
            tier_min="free", context_length=4096, capabilities=["chat", "completion"], requires_api_key=False
        )
        
        # Mistral
        self._models["mistral_large"] = ModelInfo(
            name="mistral_large", display_name="Mistral Large", provider="Mistral",
            tier_min="pro", context_length=32768, capabilities=["chat", "completion", "json", "tools"], requires_api_key=True, api_key_env="MISTRAL_API_KEY"
        )
        self._models["mistral_medium"] = ModelInfo(
            name="mistral_medium", display_name="Mistral Medium", provider="Mistral",
            tier_min="basic", context_length=32768, capabilities=["chat", "completion", "json"], requires_api_key=True, api_key_env="MISTRAL_API_KEY"
        )
        self._models["mistral_small"] = ModelInfo(
            name="mistral_small", display_name="Mistral Small", provider="Mistral",
            tier_min="free", context_length=32768, capabilities=["chat", "completion"], requires_api_key=True, api_key_env="MISTRAL_API_KEY"
        )
        
        # Cohere
        self._models["cohere_command_r"] = ModelInfo(
            name="cohere_command_r", display_name="Command R+", provider="Cohere",
            tier_min="basic", context_length=128000, capabilities=["chat", "completion", "tools"], requires_api_key=True, api_key_env="COHERE_API_KEY"
        )
        self._models["cohere_command"] = ModelInfo(
            name="cohere_command", display_name="Command", provider="Cohere",
            tier_min="free", context_length=4096, capabilities=["chat", "completion"], requires_api_key=True, api_key_env="COHERE_API_KEY"
        )
        
        # AI21
        self._models["ai21_j2_ultra"] = ModelInfo(
            name="ai21_j2_ultra", display_name="Jurassic-2 Ultra", provider="AI21",
            tier_min="pro", context_length=8192, capabilities=["completion", "chat"], requires_api_key=True, api_key_env="AI21_API_KEY"
        )
        self._models["ai21_j2_mid"] = ModelInfo(
            name="ai21_j2_mid", display_name="Jurassic-2 Mid", provider="AI21",
            tier_min="basic", context_length=8192, capabilities=["completion", "chat"], requires_api_key=True, api_key_env="AI21_API_KEY"
        )
        
        # Chinese models (from ai-bot.cn top list)
        self._models["wenxin"] = ModelInfo(
            name="wenxin", display_name="文心一言 4.0", provider="Baidu",
            tier_min="free", context_length=8192, capabilities=["chat", "completion"], requires_api_key=True, api_key_env="BAIDU_API_KEY"
        )
        self._models["tongyi"] = ModelInfo(
            name="tongyi", display_name="通义千问", provider="Alibaba",
            tier_min="free", context_length=8192, capabilities=["chat", "completion"], requires_api_key=True, api_key_env="ALIBABA_API_KEY"
        )
        self._models["hunyuan"] = ModelInfo(
            name="hunyuan", display_name="混元", provider="Tencent",
            tier_min="basic", context_length=8192, capabilities=["chat", "completion"], requires_api_key=True, api_key_env="TENCENT_API_KEY"
        )
        self._models["glm4"] = ModelInfo(
            name="glm4", display_name="GLM-4", provider="Zhipu",
            tier_min="free", context_length=128000, capabilities=["chat", "completion", "tools"], requires_api_key=True, api_key_env="ZHIPU_API_KEY"
        )
        self._models["minimax"] = ModelInfo(
            name="minimax", display_name="MiniMax Abab 6.5", provider="MiniMax",
            tier_min="free", context_length=8192, capabilities=["chat", "completion"], requires_api_key=True, api_key_env="MINIMAX_API_KEY"
        )
        self._models["spark"] = ModelInfo(
            name="spark", display_name="讯飞星火 4.0", provider="iFlytek",
            tier_min="free", context_length=8192, capabilities=["chat", "completion"], requires_api_key=True, api_key_env="IFLYTEK_API_KEY"
        )
        self._models["baichuan"] = ModelInfo(
            name="baichuan", display_name="百川 4", provider="Baichuan",
            tier_min="basic", context_length=4096, capabilities=["chat", "completion"], requires_api_key=True, api_key_env="BAICHUAN_API_KEY"
        )
        self._models["stepfun"] = ModelInfo(
            name="stepfun", display_name="Step-2", provider="Stepfun",
            tier_min="basic", context_length=8192, capabilities=["chat", "completion"], requires_api_key=True, api_key_env="STEPFUN_API_KEY"
        )
        self._models["sensechat"] = ModelInfo(
            name="sensechat", display_name="SenseChat 5", provider="SenseTime",
            tier_min="free", context_length=8192, capabilities=["chat", "completion"], requires_api_key=True, api_key_env="SENSETIME_API_KEY"
        )
        self._models["tiangong"] = ModelInfo(
            name="tiangong", display_name="天工", provider="Kunlun",
            tier_min="free", context_length=4096, capabilities=["chat", "completion"], requires_api_key=True, api_key_env="KUNLUN_API_KEY"
        )
        self._models["zhinao"] = ModelInfo(
            name="zhinao", display_name="360 智脑", provider="Qihoo 360",
            tier_min="free", context_length=4096, capabilities=["chat", "completion"], requires_api_key=True, api_key_env="QI360_API_KEY"
        )
    
    def get_model(self, name: str) -> Optional[ModelInfo]:
        return self._models.get(name)
    
    def list_models(self, tier: Optional[str] = None) -> List[str]:
        if tier is None:
            return list(self._models.keys())
        return [name for name, info in self._models.items() if self._tier_ge(info.tier_min, tier)]
    
    def list_models_with_info(self, tier: Optional[str] = None) -> List[ModelInfo]:
        if tier is None:
            return list(self._models.values())
        return [info for info in self._models.values() if self._tier_ge(info.tier_min, tier)]
    
    def _tier_ge(self, required: str, current: str) -> bool:
        order = {"free": 0, "basic": 1, "pro": 2, "enterprise": 3}
        return order.get(required, 0) <= order.get(current, 0)
    
    def get_recommended_model(self, tier: str, capability: str = "chat") -> str:
        for name, info in self._models.items():
            if self._tier_ge(info.tier_min, tier) and capability in info.capabilities:
                return name
        return "deepseek_v2_lite"
