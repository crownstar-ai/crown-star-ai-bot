# tests/test_api.py
"""
API integration tests.
"""

import pytest
from fastapi.testclient import TestClient
import json

from src.server.app import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "CrownStar Enterprise API"
    assert "version" in data


def test_health():
    response = client.get("/v1/health")
    assert response.status_code in [200, 503]  # 503 if unhealthy
    data = response.json()
    assert "status" in data
    assert "checks" in data


def test_version():
    response = client.get("/v1/system/version")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data


def test_license_validate():
    response = client.get("/v1/license/validate")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["no_license", "valid", "invalid"]


def test_chat_endpoint():
    # Requires license to be set; we'll test with free tier (no license)
    response = client.post(
        "/v1/chat/",
        json={
            "prompt": "Hello, world!",
            "project_id": "test",
            "chat_id": None,
            "temperature": 0.7,
            "max_tokens": 50,
            "modules": [],
        }
    )
    # It should return a 200 or 4xx based on license; we're just testing that it's callable
    assert response.status_code in [200, 403, 422]


def test_admin_users_endpoint():
    response = client.get("/v1/admin/users")
    # Should be 403 unless license is enterprise/pro
    assert response.status_code in [403, 200]


def test_analytics_daily_usage():
    response = client.get("/v1/analytics/usage/daily")
    # Should be 403 or 422 unless license is pro/enterprise and user_id present
    assert response.status_code in [403, 422, 200]


def test_system_status():
    response = client.get("/v1/system/status")
    assert response.status_code == 200
    data = response.json()
    assert "uptime_seconds" in data
    assert "memory_usage_mb" in data
