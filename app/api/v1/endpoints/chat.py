from typing import List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.deepseek import deepseek_client
from app.models.user import User
from app.services.chat_service import ChatService
from app.api.v1.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatStreamRequest,
    ConversationResponse,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/completions", response_model=ChatResponse)
async def chat_completion(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    对话补全
    
    调用 DeepSeek API 进行对话[reference:4]
    
    注意：legacy 模型 deepseek-chat 和 deepseek-reasoner 将于 2026年7月24日停用[reference:5]
    请使用 deepseek-v4-pro 或 deepseek-v4-flash[reference:6]
    """
    chat_service = ChatService(session)
    
    # 构建消息
    messages = [
        {"role": "system", "content": request.system_prompt or "You are a helpful assistant."},
    ] + [{"role": msg.role, "content": msg.content} for msg in request.messages]
    
    # 调用 DeepSeek
    response = await deepseek_client.chat_completion(
        messages=messages,
        model=request.model,
        temperature=request.temperature,
        top_p=request.top_p,
        max_tokens=request.max_tokens,
        thinking=request.thinking,
        reasoning_effort=request.reasoning_effort,
    )
    
    # 保存对话记录
    conversation = await chat_service.save_conversation(
        user_id=current_user.id,
        messages=messages,
        response=response.choices[0].message.content,
        model=response.model,
        tokens_used=response.usage.total_tokens if response.usage else 0,
    )
    
    return ChatResponse(
        id=response.id,
        model=response.model,
        content=response.choices[0].message.content,
        usage={
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        },
        finish_reason=response.choices[0].finish_reason,
        conversation_id=conversation.id,
    )


@router.post("/completions/stream")
async def chat_completion_stream(
    request: ChatStreamRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    流式对话补全
    
    使用 Server-Sent Events (SSE) 实时返回 DeepSeek 响应
    """
    messages = [
        {"role": "system", "content": request.system_prompt or "You are a helpful assistant."},
    ] + [{"role": msg.role, "content": msg.content} for msg in request.messages]
    
    async def generate():
        full_response = ""
        try:
            async for chunk in deepseek_client.chat_completion_stream(
                messages=messages,
                model=request.model,
                temperature=request.temperature,
                top_p=request.top_p,
                max_tokens=request.max_tokens,
                thinking=request.thinking,
                reasoning_effort=request.reasoning_effort,
            ):
                full_response += chunk
                yield f"data: {chunk}\n\n"
            
            # 保存对话记录
            chat_service = ChatService(session)
            await chat_service.save_conversation(
                user_id=current_user.id,
                messages=messages,
                response=full_response,
                model=request.model or "deepseek-v4-pro",
                tokens_used=0,  # 流式无法获取准确 token 数
            )
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )