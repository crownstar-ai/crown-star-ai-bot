from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import time
import json

# Import our new memory modules
from memory.immortal_notebook import ImmortalNotebook
from memory.project_manager import ProjectManager
from memory.context_weaver import ContextWeaver
from bootstrap.model_wrapper import CrownStarBootstrap

# Import license middleware (if exists)
try:
    from middleware.license_middleware import LicenseMiddleware
except ImportError:
    LicenseMiddleware = None

# Initialize memory components
notebook = ImmortalNotebook()
project_manager = ProjectManager()
context_weaver = ContextWeaver()

# Dummy model adapter for now – replace with actual vLLM call
def dummy_model_adapter(prompt: str, **kwargs) -> str:
    return f"[Simulated response to: {prompt[:100]}...]"

# Create bootstrap instance with dummy adapter
bootstrap = CrownStarBootstrap(dummy_model_adapter)

app = FastAPI(title="CrownStar API", version="7.0.1")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add license middleware if available
if LicenseMiddleware:
    app.add_middleware(LicenseMiddleware)

# ---------- Health Endpoint ----------
@app.get("/v1/health")
async def health():
    return {
        "status": "healthy",
        "version": "7.0.1",
        "timestamp": time.time(),
        "memory_available": True
    }

# ---------- Project Endpoints ----------
class CreateProjectRequest(BaseModel):
    name: str
    description: Optional[str] = ""

@app.post("/v1/project/create")
async def create_project(req: CreateProjectRequest):
    return project_manager.create_project(req.name, req.description)

@app.get("/v1/project/list")
async def list_projects():
    return project_manager.list_projects()

@app.get("/v1/project/{project_id}")
async def get_project(project_id: str):
    project = project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@app.post("/v1/project/{project_id}/chat")
async def add_chat_to_project(project_id: str, chat_id: str):
    result = project_manager.add_chat_to_project(project_id, chat_id)
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "added"}

# ---------- Chat & Memory Endpoints ----------
class MemoryChatRequest(BaseModel):
    prompt: str
    project_id: str
    chat_id: Optional[str] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 2048

@app.post("/v1/chat/memory")
async def chat_with_memory(req: MemoryChatRequest):
    result = bootstrap.chat(
        prompt=req.prompt,
        project_id=req.project_id,
        chat_id=req.chat_id,
        temperature=req.temperature,
        max_tokens=req.max_tokens
    )
    return result

@app.get("/v1/project/{project_id}/memory")
async def get_project_memory(project_id: str):
    return notebook.get_project_memory(project_id)

@app.get("/v1/chat/{chat_id}/history")
async def get_chat_history(chat_id: str):
    return notebook.get_chat_history(chat_id)

@app.post("/v1/project/{project_id}/search")
async def search_memory(project_id: str, query: str):
    return notebook.search_memory(project_id, query)

# ---------- Root ----------
@app.get("/")
async def root():
    return {"message": "CrownStar API", "version": "7.0.1"}
