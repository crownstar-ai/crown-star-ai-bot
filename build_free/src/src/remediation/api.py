# remediation/api.py – REST API for auto‑remediation
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
from .engine.engine import get_remediation_engine
from .actions.actions import RemediationActions
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/remediation", tags=["Auto‑Remediation"])

class TriggerRemediationRequest(BaseModel):
    policy_id: str
    force: bool = False

class AddPolicyRequest(BaseModel):
    id: str
    condition: str
    action: str
    params: Optional[Dict] = {}
    cooldown_seconds: int = 300
    severity: str = "medium"
    enabled: bool = True

@router.get("/status")
async def remediation_status(user: dict = Depends(require_permission("admin"))):
    engine = get_remediation_engine()
    status = engine.get_status()
    return status

@router.get("/history")
async def remediation_history(limit: int = 50, user: dict = Depends(require_permission("admin"))):
    engine = get_remediation_engine()
    history = engine.get_history(limit)
    return {"history": history}

@router.get("/policies")
async def list_policies(user: dict = Depends(require_permission("admin"))):
    engine = get_remediation_engine()
    policies = engine.config["policies"]
    return {"policies": policies}

@router.post("/policies")
async def add_policy(req: AddPolicyRequest, user: dict = Depends(require_permission("admin"))):
    engine = get_remediation_engine()
    new_policy = req.dict()
    engine.config["policies"].append(new_policy)
    # Save to config file
    with open("config/remediation/policies.json", "w") as f:
        json.dump(engine.config, f, indent=2)
    return {"message": "Policy added", "policy": new_policy}

@router.delete("/policies/{policy_id}")
async def delete_policy(policy_id: str, user: dict = Depends(require_permission("admin"))):
    engine = get_remediation_engine()
    original_len = len(engine.config["policies"])
    engine.config["policies"] = [p for p in engine.config["policies"] if p["id"] != policy_id]
    if len(engine.config["policies"]) == original_len:
        raise HTTPException(404, "Policy not found")
    with open("config/remediation/policies.json", "w") as f:
        json.dump(engine.config, f, indent=2)
    return {"message": f"Policy {policy_id} deleted"}

@router.post("/trigger")
async def trigger_remediation(req: TriggerRemediationRequest, user: dict = Depends(require_permission("admin"))):
    """Manually trigger remediation for a policy"""
    engine = get_remediation_engine()
    # Find policy
    policy = next((p for p in engine.config["policies"] if p["id"] == req.policy_id), None)
    if not policy:
        raise HTTPException(404, "Policy not found")
    # Force ignore cooldown? Use a temporary context
    context = engine._get_current_context()
    condition_met = engine._evaluate_condition(policy["condition"], context)
    if not condition_met and not req.force:
        return {"message": f"Condition not met for policy {req.policy_id}. Use force=true to override."}
    action_method = getattr(engine.actions, policy["action"], None)
    if not action_method:
        raise HTTPException(500, f"Action {policy['action']} not found")
    params = policy.get("params", {})
    success = action_method(**params)
    engine._record_remediation(policy["id"], policy["action"], success, f"manual trigger, force={req.force}")
    return {"success": success, "action": policy["action"], "policy_id": req.policy_id}

@router.post("/run")
async def run_remediation_cycle(user: dict = Depends(require_permission("admin"))):
    """Force an immediate remediation evaluation cycle"""
    engine = get_remediation_engine()
    results = engine.evaluate_and_remediate()
    return {"results": results}
