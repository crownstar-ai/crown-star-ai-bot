# base_adapter.py – Abstract interface for all language model adapters
from abc import ABC, abstractmethod

class LanguageModelAdapter(ABC):
    @abstractmethod
    async def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        pass
    @abstractmethod
    def get_model_info(self) -> dict:
        pass
