import asyncio
import logging
from typing import Optional, List, Dict, Any, AsyncGenerator
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class DeepSeekClient:
    """DeepSeek API 企业级客户端"""
    
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            timeout=settings.DEEPSEEK_TIMEOUT,
            max_retries=settings.DEEPSEEK_MAX_RETRIES,
        )
        self.default_model = settings.DEEPSEEK_MODEL
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 1.0,
        top_p: float = 1.0,
        max_tokens: Optional[int] = None,
        thinking: bool = True,
        reasoning_effort: str = "high",
        stream: bool = False,
        **kwargs
    ) -> ChatCompletion:
        """
        对话补全 - 企业级调用
        
        重要：根据 DeepSeek 官方文档，legacy 模型 deepseek-chat 和 deepseek-reasoner
        将于 2026年7月24日 停用，请使用 deepseek-v4-pro 或 deepseek-v4-flash[reference:0][reference:1]
        """
        model = model or self.default_model
        
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                stream=stream,
                reasoning_effort=reasoning_effort,
                extra_body={"thinking": {"type": "enabled" if thinking else "disabled"}},
                **kwargs
            )
            
            logger.info(
                "deepseek_chat_completion_success",
                model=model,
                tokens=response.usage.total_tokens if response.usage else 0,
                finish_reason=response.choices[0].finish_reason if response.choices else None,
            )
            return response
            
        except Exception as e:
            logger.error(
                "deepseek_chat_completion_failed",
                error=str(e),
                model=model,
            )
            raise
    
    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 1.0,
        top_p: float = 1.0,
        max_tokens: Optional[int] = None,
        thinking: bool = True,
        reasoning_effort: str = "high",
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式对话补全"""
        model = model or self.default_model
        
        try:
            stream = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                stream=True,
                reasoning_effort=reasoning_effort,
                extra_body={"thinking": {"type": "enabled" if thinking else "disabled"}},
                **kwargs
            )
            
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error("deepseek_stream_failed", error=str(e))
            raise


deepseek_client = DeepSeekClient()