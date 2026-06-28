# chaos/platform/chaos_mesh/client.py – Chaos Mesh API client
import requests
import json
import time
from typing import Dict, List, Optional, Any
from kubernetes import client, config
from kubernetes.client import ApiException

class ChaosMeshClient:
    def __init__(self, api_url: str = None, namespace: str = "chaos-testing"):
        self.api_url = api_url or os.environ.get("CHAOS_MESH_URL", "http://chaos-mesh:2333")
        self.namespace = namespace
        self._k8s_client = None
        self._init_k8s()
    
    def _init_k8s(self):
        try:
            config.load_incluster_config()
            self._k8s_client = client.CustomObjectsApi()
        except:
            config.load_kube_config()
            self._k8s_client = client.CustomObjectsApi()
    
    def create_pod_chaos(self, name: str, action: str, pod_selector: Dict, duration: str) -> Dict:
        """Create PodChaos (pod-kill, pod-failure, container-kill)"""
        body = {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "PodChaos",
            "metadata": {"name": name, "namespace": self.namespace},
            "spec": {
                "action": action,
                "mode": "one",
                "selector": {"namespaces": [self.namespace], "labelSelectors": pod_selector},
                "duration": duration,
                "scheduler": {"cron": "@every 30s"}
            }
        }
        try:
            resp = self._k8s_client.create_namespaced_custom_object(
                group="chaos-mesh.org", version="v1alpha1", namespace=self.namespace,
                plural="podchaos", body=body
            )
            return resp
        except ApiException as e:
            return {"error": str(e)}
    
    def create_network_chaos(self, name: str, action: str, pod_selector: Dict, duration: str,
                              delay: str = None, loss: str = None, duplicate: str = None) -> Dict:
        """Create NetworkChaos (delay, loss, duplicate, corrupt)"""
        body = {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "NetworkChaos",
            "metadata": {"name": name, "namespace": self.namespace},
            "spec": {
                "action": action,
                "mode": "one",
                "selector": {"namespaces": [self.namespace], "labelSelectors": pod_selector},
                "duration": duration,
                "scheduler": {"cron": "@every 30s"}
            }
        }
        if delay:
            body["spec"]["delay"] = {"latency": delay, "correlation": "100", "jitter": "0ms"}
        if loss:
            body["spec"]["loss"] = {"loss": loss, "correlation": "100"}
        if duplicate:
            body["spec"]["duplicate"] = {"duplicate": duplicate, "correlation": "100"}
        try:
            resp = self._k8s_client.create_namespaced_custom_object(
                group="chaos-mesh.org", version="v1alpha1", namespace=self.namespace,
                plural="networkchaos", body=body
            )
            return resp
        except ApiException as e:
            return {"error": str(e)}
    
    def create_stress_chaos(self, name: str, pod_selector: Dict, duration: str,
                            cpu_stress: bool = False, cpu_workers: int = 1,
                            memory_stress: bool = False, memory_size: str = "100MB") -> Dict:
        """Create StressChaos (CPU/memory stress)"""
        body = {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "StressChaos",
            "metadata": {"name": name, "namespace": self.namespace},
            "spec": {
                "mode": "one",
                "selector": {"namespaces": [self.namespace], "labelSelectors": pod_selector},
                "duration": duration,
                "scheduler": {"cron": "@every 30s"},
                "stressors": {}
            }
        }
        if cpu_stress:
            body["spec"]["stressors"]["cpu"] = {"workers": cpu_workers, "load": 100}
        if memory_stress:
            body["spec"]["stressors"]["memory"] = {"size": memory_size, "workers": 1}
        try:
            resp = self._k8s_client.create_namespaced_custom_object(
                group="chaos-mesh.org", version="v1alpha1", namespace=self.namespace,
                plural="stresschaos", body=body
            )
            return resp
        except ApiException as e:
            return {"error": str(e)}
    
    def delete_chaos(self, kind: str, name: str) -> bool:
        try:
            self._k8s_client.delete_namespaced_custom_object(
                group="chaos-mesh.org", version="v1alpha1", namespace=self.namespace,
                plural=kind.lower(), name=name
            )
            return True
        except ApiException:
            return False
    
    def list_chaos(self, kind: str) -> List[Dict]:
        try:
            resp = self._k8s_client.list_namespaced_custom_object(
                group="chaos-mesh.org", version="v1alpha1", namespace=self.namespace,
                plural=kind.lower()
            )
            return resp.get("items", [])
        except ApiException:
            return []

_chaos_mesh = None
def get_chaos_mesh_client():
    global _chaos_mesh
    if _chaos_mesh is None:
        _chaos_mesh = ChaosMeshClient()
    return _chaos_mesh
