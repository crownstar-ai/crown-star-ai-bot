# mesh/api.py – REST API for service mesh status and traffic management
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional
import subprocess
import json
import os
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/mesh", tags=["Service Mesh"])

class TrafficSplitRequest(BaseModel):
    namespace: str = "crownstar"
    service: str = "crownstar-api"
    weights: Dict[str, int]  # e.g., {"stable": 90, "canary": 10}

@router.get("/status")
async def mesh_status(user: dict = Depends(require_permission("admin"))):
    """Detect which service mesh is active and return status"""
    status = {"mesh": "none", "sidecar_injected": False, "mtls_enabled": False}
    # Check for Istio
    try:
        result = subprocess.run(["kubectl", "get", "pods", "-n", "crownstar", "-l", "app=crownstar-api", "-o", "json"], capture_output=True, text=True)
        pods = json.loads(result.stdout)
        for pod in pods.get("items", []):
            containers = pod.get("spec", {}).get("containers", [])
            if any("istio-proxy" in c.get("name", "") for c in containers):
                status["mesh"] = "istio"
                status["sidecar_injected"] = True
                break
    except:
        pass
    # Check for Linkerd
    try:
        result = subprocess.run(["kubectl", "get", "pod", "-n", "crownstar", "-l", "app=crownstar-api", "-o", "json"], capture_output=True, text=True)
        pods = json.loads(result.stdout)
        for pod in pods.get("items", []):
            annotations = pod.get("metadata", {}).get("annotations", {})
            if annotations.get("linkerd.io/inject") == "enabled":
                status["mesh"] = "linkerd"
                status["sidecar_injected"] = True
                break
    except:
        pass
    # Check for Consul
    try:
        result = subprocess.run(["kubectl", "get", "pod", "-n", "crownstar", "-l", "app=crownstar-api", "-o", "json"], capture_output=True, text=True)
        pods = json.loads(result.stdout)
        for pod in pods.get("items", []):
            labels = pod.get("metadata", {}).get("labels", {})
            if labels.get("consul.hashicorp.com/connect-inject-status") == "injected":
                status["mesh"] = "consul"
                status["sidecar_injected"] = True
                break
    except:
        pass
    return status

@router.post("/traffic/split")
async def traffic_split(req: TrafficSplitRequest, user: dict = Depends(require_permission("admin"))):
    """Apply traffic splitting using VirtualService (Istio) or TrafficSplit (Linkerd)"""
    mesh_status_data = await mesh_status(user)
    mesh = mesh_status_data.get("mesh")
    if mesh == "istio":
        vs_yaml = f'''
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: crownstar-api-split
  namespace: {req.namespace}
spec:
  hosts:
  - {req.service}
  http:
  - route:
'''
        for version, weight in req.weights.items():
            vs_yaml += f'''    - destination:
          host: {req.service}
          subset: {version}
        weight: {weight}
'''
        with open("/tmp/vs.yaml", "w") as f:
            f.write(vs_yaml)
        subprocess.run(["kubectl", "apply", "-f", "/tmp/vs.yaml"], check=True)
        return {"message": f"Traffic split applied (Istio): {req.weights}"}
    elif mesh == "linkerd":
        ts_yaml = f'''
apiVersion: split.smi-spec.io/v1alpha2
kind: TrafficSplit
metadata:
  name: crownstar-api-split
  namespace: {req.namespace}
spec:
  service: {req.service}
  backends:
'''
        for version, weight in req.weights.items():
            ts_yaml += f'''  - service: {req.service}-{version}
    weight: {weight}
'''
        with open("/tmp/ts.yaml", "w") as f:
            f.write(ts_yaml)
        subprocess.run(["kubectl", "apply", "-f", "/tmp/ts.yaml"], check=True)
        return {"message": f"Traffic split applied (Linkerd): {req.weights}"}
    else:
        raise HTTPException(400, "No service mesh detected or unsupported mesh")

@router.get("/canary/status")
async def canary_status(user: dict = Depends(require_permission("admin"))):
    """Return current canary deployment weights"""
    mesh_data = await mesh_status(user)
    if mesh_data.get("mesh") == "istio":
        result = subprocess.run(["kubectl", "get", "vs", "crownstar-api-split", "-n", "crownstar", "-o", "json"], capture_output=True, text=True)
        if result.returncode == 0:
            vs = json.loads(result.stdout)
            routes = vs.get("spec", {}).get("http", [{}])[0].get("route", [])
            weights = {r["destination"]["subset"]: r["weight"] for r in routes}
            return {"weights": weights}
    return {"message": "Canary status not available"}

@router.post("/mtls/enable")
async def enable_mtls(user: dict = Depends(require_permission("admin"))):
    mesh_data = await mesh_status(user)
    if mesh_data.get("mesh") == "istio":
        subprocess.run(["kubectl", "apply", "-f", "config/mesh/istio/peerauthentication.yaml"], check=True)
        return {"message": "mTLS enabled (Istio STRICT mode)"}
    elif mesh_data.get("mesh") == "linkerd":
        subprocess.run(["kubectl", "annotate", "namespace", "crownstar", "linkerd.io/mtls=enabled"], check=True)
        return {"message": "mTLS enabled (Linkerd)"}
    else:
        raise HTTPException(400, "No mesh or mTLS not supported")
