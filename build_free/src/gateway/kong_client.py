# gateway/kong_client.py – Python client for Kong Admin API
import requests
import json
import os
from typing import Dict, List, Optional

KONG_ADMIN_URL = os.environ.get("KONG_ADMIN_URL", "http://localhost:8001")

class KongClient:
    @staticmethod
    def _request(method: str, path: str, data: dict = None) -> dict:
        url = f"{KONG_ADMIN_URL}/{path.lstrip('/')}"
        resp = requests.request(method, url, json=data)
        resp.raise_for_status()
        return resp.json()
    
    @staticmethod
    def list_routes() -> List[dict]:
        return KongClient._request("GET", "/routes")["data"]
    
    @staticmethod
    def list_services() -> List[dict]:
        return KongClient._request("GET", "/services")["data"]
    
    @staticmethod
    def create_service(name: str, url: str) -> dict:
        return KongClient._request("POST", "/services", data={"name": name, "url": url})
    
    @staticmethod
    def create_route(service_name: str, paths: List[str], methods: List[str] = None) -> dict:
        data = {"service": {"name": service_name}, "paths": paths}
        if methods:
            data["methods"] = methods
        return KongClient._request("POST", "/routes", data=data)
    
    @staticmethod
    def enable_plugin(service_name: str, plugin_name: str, config: dict) -> dict:
        data = {"name": plugin_name, "service": {"name": service_name}, "config": config}
        return KongClient._request("POST", "/plugins", data=data)
    
    @staticmethod
    def sync_crownstar_routes():
        """Synchronise CrownStar services with Kong declarative config"""
        # This would be used when running Kong in db mode; for dbless we use declarative config
        print("For dbless mode, use declarative config file. For db mode, use this method.")
        return True

    @staticmethod
    def get_rate_limits(consumer: str = None) -> dict:
        if consumer:
            return KongClient._request("GET", f"/consumers/{consumer}/rate-limiting")
        return KongClient._request("GET", "/rate-limiting")

    @staticmethod
    def set_rate_limit(consumer: str, minute: int = None, hour: int = None, day: int = None) -> dict:
        config = {}
        if minute: config["minute"] = minute
        if hour: config["hour"] = hour
        if day: config["day"] = day
        return KongClient._request("POST", f"/consumers/{consumer}/plugins", data={
            "name": "rate-limiting",
            "config": config
        })
