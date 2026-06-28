# agent/api.py – REST API for agent orchestration
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Optional
from .core import get_agent_manager
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/agent", tags=["AI Agent"])

class AgentCreateRequest(BaseModel):
    name: str
    type: str = "react"  # react, autogpt
    max_iterations: int = 10

class AgentRunRequest(BaseModel):
    task: str

@router.post("/create")
async def create_agent(req: AgentCreateRequest, user=Depends(require_permission("admin"))):
    """Create a new agent instance."""
    mgr = get_agent_manager()
    name = mgr.create_agent(req.name, req.type, req.max_iterations)
    return {"agent": name, "type": req.type}

@router.post("/{agent_name}/run")
async def run_agent(agent_name: str, req: AgentRunRequest, background_tasks: BackgroundTasks, user=Depends(require_permission("admin"))):
    """Run an agent on a given task."""
    mgr = get_agent_manager()
    result = mgr.run_agent(agent_name, req.task)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result

@router.get("/{agent_name}/stop")
async def stop_agent(agent_name: str, user=Depends(require_permission("admin"))):
    """Stop a running agent."""
    mgr = get_agent_manager()
    mgr.stop_agent(agent_name)
    return {"status": "stopped", "agent": agent_name}

@router.get("/list")
async def list_agents(user=Depends(require_permission("admin"))):
    """List all agents."""
    mgr = get_agent_manager()
    return {"agents": mgr.list_agents()}

@router.get("/tools")
async def list_tools(user=Depends(require_permission("admin"))):
    """List available tools for agents."""
    mgr = get_agent_manager()
    tools = mgr.tool_registry.list_tools()
    return {"tools": tools}
