# serverless/api.py – REST API for serverless deployment control
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
import subprocess
import os
import json
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/serverless", tags=["Serverless"])

class DeployRequest(BaseModel):
    provider: str  # aws, azure, cloudflare
    environment: str = "prod"

@router.post("/deploy")
async def serverless_deploy(req: DeployRequest, background: BackgroundTasks, user: dict = Depends(require_permission("admin"))):
    """Trigger deployment to serverless provider"""
    if req.provider == "aws":
        script = "scripts/serverless/deploy_aws.sh"
    elif req.provider == "azure":
        script = "scripts/serverless/deploy_azure.sh"
    elif req.provider == "cloudflare":
        script = "scripts/serverless/deploy_cf.sh"
    else:
        raise HTTPException(400, "Provider must be aws, azure, or cloudflare")
    
    if not os.path.exists(script):
        raise HTTPException(404, f"Deployment script not found: {script}")
    
    def run_deploy():
        result = subprocess.run(["bash", script], capture_output=True, text=True)
        # Could log result
        print(f"Deployment to {req.provider} completed: {result.stdout}")
    
    background.add_task(run_deploy)
    return {"message": f"Deployment to {req.provider} started in background", "script": script}

@router.get("/config")
async def serverless_config(user: dict = Depends(require_permission("user"))):
    """Return current serverless configuration"""
    configs = {}
    for provider, file in [("aws", "serverless.yml"), ("azure", "src/serverless/azure/function.json"), ("cloudflare", "wrangler.toml")]:
        if os.path.exists(file):
            with open(file, "r") as f:
                configs[provider] = f.read(500)  # truncated
    return {"available_providers": ["aws", "azure", "cloudflare"], "config_snippets": configs}

@router.get("/status")
async def serverless_status(user: dict = Depends(require_permission("user"))):
    # Check if any serverless deployments are active (stub)
    return {
        "aws_lambda": "unknown (run deploy script)",
        "azure_functions": "unknown",
        "cloudflare_workers": "unknown"
    }
