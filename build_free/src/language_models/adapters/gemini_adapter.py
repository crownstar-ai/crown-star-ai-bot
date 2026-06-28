from .base_adapter import LanguageModelAdapter
import os

class GeminiAdapter(LanguageModelAdapter):
    def __init__(self, api_key: str = None, model: str = 'gemini-pro'): pass
    async def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        return '[Gemini would respond here – API key not configured]'
    def get_model_info(self) -> dict:
        return {'name': 'Gemini Pro', 'provider': 'Google'}
