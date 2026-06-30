# src/language_models/model_router.py
"""
Routes chat requests to the appropriate language model (DeepSeek, OpenAI, etc.).
"""

import os
import time
import asyncio
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

from src.core.logging_config import get_logger
from src.core.exceptions import DependencyError, TimeoutError
from src.language_models.adapters.deepseek_adapter import DeepSeekAdapter
from src.language_models.adapters.openai_adapter import OpenAIAdapter

logger = get_logger(__name__)


@dataclass
class ModelResponse:
    text: str
    tokens_used: int
    latency_ms: float


class ModelRouter:
    """
    Routes requests to the best model based on configuration and availability.
    Supports multiple backends with fallback.
    """
    
    def __init__(self):
        self.models = {}
        self._init_adapters()
    
    def _init_adapters(self):
        """Initialize available model adapters."""
        # DeepSeek (primary)
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if api_key:
            try:
                self.models["deepseek_v2_lite"] = DeepSeekAdapter(
                    model_version="v2_lite",
                    api_key=api_key
                )
                self.models["deepseek_v3"] = DeepSeekAdapter(
                    model_version="v3",
                    api_key=api_key
                )
                logger.info("DeepSeek adapters initialized")
            except Exception as e:
                logger.error(f"Failed to initialize DeepSeek: {e}")
        
        # OpenAI (fallback)
        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key:
            try:
                self.models["gpt4"] = OpenAIAdapter(model="gpt-4", api_key=openai_key)
                self.models["gpt35"] = OpenAIAdapter(model="gpt-3.5-turbo", api_key=openai_key)
                logger.info("OpenAI adapters initialized")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI: {e}")
        
        # If no models available, we'll use a mock for testing
        if not self.models:
            logger.warning("No model adapters available. Using mock adapter.")
            self.models["mock"] = self._mock_adapter
    
    def _mock_adapter(self, prompt: str, **kwargs) -> ModelResponse:
        """Mock adapter for testing."""
        return ModelResponse(
            text=f"[MOCK] Response to: {prompt[:50]}...",
            tokens_used=len(prompt.split()),
            latency_ms=10.0
        )
    
    async def generate(
        self,
        prompt: str,
        model: str = "deepseek_v2_lite",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout_seconds: int = 30,
    ) -> Tuple[str, int]:
        """
        Generate a response from the specified model.
        Returns (response_text, tokens_used).
        """
        if model not in self.models:
            logger.warning(f"Model '{model}' not found, falling back to first available")
            model = next(iter(self.models.keys()))
        
        adapter = self.models[model]
        start_time = time.perf_counter()
        
        try:
            # Call adapter with timeout
            if asyncio.iscoroutinefunction(adapter):
                response = await asyncio.wait_for(
                    adapter(prompt, max_tokens=max_tokens, temperature=temperature),
                    timeout=timeout_seconds
                )
            else:
                # Synchronous adapter (run in executor)
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(adapter, prompt, max_tokens=max_tokens, temperature=temperature)
                    response = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, lambda: future.result()),
                        timeout=timeout_seconds
                    )
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(f"Generated response from {model} in {latency_ms:.0f}ms")
            
            # Extract text and token count (if available)
            text = response.get("text", str(response))
            tokens_used = response.get("tokens_used", len(text.split()))
            return text, tokens_used
            
        except asyncio.TimeoutError:
            logger.error(f"Model {model} timed out after {timeout_seconds}s")
            raise TimeoutError(f"Model {model} generation")
        except Exception as e:
            logger.error(f"Model {model} error: {e}", exc_info=True)
            raise DependencyError("language_model", {"model": model, "error": str(e)})
    
    def list_models(self) -> list:
        """List available models."""
        return list(self.models.keys())
