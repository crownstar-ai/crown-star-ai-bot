# src/infra/api.py – REST API for infrastructure status and actions
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional
import subprocess
import json
import os
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/infra", tags=["Infrastructure"])

class InfraDeployRequest(BaseModel):
    tool: str = "terraform"
    environment: str = "dev"

@router.get("/status")
async def infra_status(user: dict = Depends(require_permission("admin"))):
    """Return current infrastructure outputs (from state)"""
    status = {}
    # Try to read Terraform outputs
    tf_output_file = "iac/terraform/aws/terraform.tfstate"
    if os.path.exists(tf_output_file):
        with open(tf_output_file, 'r') as f:
            state = json.load(f)
            outputs = state.get("outputs", {})
            status = {k: v.get("value") for k, v in outputs.items()}
    # Fallback to environment variables
    if not status:
        status = {
            "vpc_id": os.environ.get("VPC_ID", "unknown"),
            "eks_cluster": os.environ.get("EKS_CLUSTER", "unknown"),
            "rds_endpoint": os.environ.get("RDS_ENDPOINT", "unknown")
        }
    return status

@router.post("/plan")
async def infra_plan(req: InfraDeployRequest, user: dict = Depends(require_permission("admin"))):
    """Run plan for the specified IaC tool"""
    cwd = f"iac/{req.tool}/aws"
    if not os.path.exists(cwd):
        raise HTTPException(404, f"Tool {req.tool} not found")
    if req.tool == "terraform":
        cmd = ["terraform", "plan", "-out=tfplan"]
    elif req.tool == "pulumi":
        cmd = ["pulumi", "preview"]
    elif req.tool == "cdk":
        cmd = ["npx", "cdk", "diff"]
    else:
        raise HTTPException(400, "Unsupported tool")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}

@router.post("/apply")
async def infra_apply(req: InfraDeployRequest, user: dict = Depends(require_permission("admin"))):
    """Apply infrastructure changes"""
    cwd = f"iac/{req.tool}/aws"
    if req.tool == "terraform":
        cmd = ["terraform", "apply", "-auto-approve", "tfplan"]
    elif req.tool == "pulumi":
        cmd = ["pulumi", "up", "--yes"]
    elif req.tool == "cdk":
        cmd = ["npx", "cdk", "deploy", "--require-approval", "never"]
    else:
        raise HTTPException(400, "Unsupported tool")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode == 0:
        return {"message": "Deployment successful", "output": result.stdout}
    raise HTTPException(500, f"Deployment failed: {result.stderr}")

@router.post("/outputs")
async def infra_outputs(user: dict = Depends(require_permission("admin"))):
    """Get infrastructure outputs (e.g., for CrownStar config)"""
    # Parse outputs from Terraform/Pulumi/CDK
    outputs = {}
    tf_output_file = "iac/terraform/aws/terraform.tfstate"
    if os.path.exists(tf_output_file):
        with open(tf_output_file, 'r') as f:
            state = json.load(f)
            outputs = state.get("outputs", {})
    return outputs
