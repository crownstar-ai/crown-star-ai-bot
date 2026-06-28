# apiversioning/version_registry.py – Register API versions and sunset policies
import json
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

class VersionStatus(Enum):
    CURRENT = "current"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"
    DEPRECATED = "deprecated"

@dataclass
class APIVersion:
    version: str
    status: VersionStatus
    introduced_at: date
    deprecated_at: Optional[date] = None
    sunset_at: Optional[date] = None
    removed_at: Optional[date] = None
    changelog_url: Optional[str] = None
    documentation_url: Optional[str] = None
    base_path: str = ""  # URL prefix, e.g., "/v1"

class VersionRegistry:
    def __init__(self, config_path: str = "config/apiversioning/versions.json"):
        self.config_path = config_path
        self.versions: Dict[str, APIVersion] = {}
        self.default_version = "v2"
        self._load_versions()
    
    def _load_versions(self):
        default = {
            "versions": [
                {
                    "version": "v1",
                    "status": "deprecated",
                    "introduced_at": "2024-01-01",
                    "deprecated_at": "2025-06-01",
                    "sunset_at": "2025-12-31",
                    "base_path": "/v1",
                    "changelog_url": "/docs/changelog#v1"
                },
                {
                    "version": "v2",
                    "status": "current",
                    "introduced_at": "2024-06-01",
                    "base_path": "/v2",
                    "changelog_url": "/docs/changelog#v2"
                },
                {
                    "version": "v3",
                    "status": "deprecated",
                    "introduced_at": "2025-01-01",
                    "deprecated_at": "2025-06-01",
                    "sunset_at": "2026-06-01",
                    "base_path": "/v3",
                    "changelog_url": "/docs/changelog#v3"
                }
            ],
            "default_version": "v2"
        }
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                data = json.load(f)
                default.update(data)
        for v in default["versions"]:
            self.versions[v["version"]] = APIVersion(
                version=v["version"],
                status=VersionStatus(v["status"]),
                introduced_at=date.fromisoformat(v["introduced_at"]),
                deprecated_at=date.fromisoformat(v["deprecated_at"]) if v.get("deprecated_at") else None,
                sunset_at=date.fromisoformat(v["sunset_at"]) if v.get("sunset_at") else None,
                base_path=v.get("base_path", f"/{v['version']}"),
                changelog_url=v.get("changelog_url"),
                documentation_url=v.get("documentation_url")
            )
        self.default_version = default["default_version"]
    
    def save(self):
        data = {
            "versions": [
                {
                    "version": v.version,
                    "status": v.status.value,
                    "introduced_at": v.introduced_at.isoformat(),
                    "deprecated_at": v.deprecated_at.isoformat() if v.deprecated_at else None,
                    "sunset_at": v.sunset_at.isoformat() if v.sunset_at else None,
                    "base_path": v.base_path,
                    "changelog_url": v.changelog_url,
                    "documentation_url": v.documentation_url
                } for v in self.versions.values()
            ],
            "default_version": self.default_version
        }
        with open(self.config_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_version(self, version: str) -> Optional[APIVersion]:
        return self.versions.get(version)
    
    def list_versions(self) -> List[APIVersion]:
        return list(self.versions.values())
    
    def get_status(self, version: str) -> Optional[VersionStatus]:
        v = self.get_version(version)
        return v.status if v else None
    
    def deprecate_version(self, version: str, deprecation_date: date) -> bool:
        v = self.get_version(version)
        if not v:
            return False
        v.status = VersionStatus.DEPRECATED
        v.deprecated_at = deprecation_date
        self.save()
        return True
    
    def sunset_version(self, version: str, sunset_date: date) -> bool:
        v = self.get_version(version)
        if not v:
            return False
        v.status = VersionStatus.SUNSET
        v.sunset_at = sunset_date
        self.save()
        return True
    
    def is_sunset(self, version: str) -> bool:
        v = self.get_version(version)
        if not v:
            return True
        if v.status == VersionStatus.SUNSET:
            return True
        if v.sunset_at and v.sunset_at <= date.today():
            return True
        return False
    
    def is_deprecated(self, version: str) -> bool:
        v = self.get_version(version)
        if not v:
            return True
        if v.status == VersionStatus.DEPRECATED:
            return True
        if v.deprecated_at and v.deprecated_at <= date.today():
            return True
        return False
    
    def get_deprecation_headers(self, version: str) -> Dict[str, str]:
        """Return HTTP headers for deprecation/sunset warnings"""
        headers = {}
        v = self.get_version(version)
        if not v:
            headers["X-API-Version-Status"] = "removed"
            return headers
        if v.status == VersionStatus.DEPRECATED:
            headers["X-API-Version-Status"] = "deprecated"
            if v.sunset_at:
                headers["Sunset"] = v.sunset_at.strftime("%a, %d %b %Y %H:%M:%S GMT")
                headers["X-API-Sunset-Date"] = v.sunset_at.isoformat()
                days_left = (v.sunset_at - date.today()).days
                headers["X-API-Sunset-Days-Left"] = str(days_left)
        elif v.status == VersionStatus.SUNSET:
            headers["X-API-Version-Status"] = "sunset"
            headers["X-API-Sunset-Date"] = v.sunset_at.isoformat() if v.sunset_at else ""
        else:
            headers["X-API-Version-Status"] = "current"
        return headers

_version_registry = None
def get_version_registry():
    global _version_registry
    if _version_registry is None:
        _version_registry = VersionRegistry()
    return _version_registry
