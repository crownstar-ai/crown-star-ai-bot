# apiversioning/openapi_generator.py – Generate OpenAPI spec per version
from fastapi import FastAPI
import json
from pathlib import Path

def generate_versioned_openapi(version: str, base_app: FastAPI, output_path: str = None):
    """Generate OpenAPI JSON for a specific API version"""
    # This would require filtering routes by version prefix
    # Simplified stub
    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": f"CrownStar API ({version})",
            "version": version[1:] if version.startswith("v") else version,
            "description": f"CrownStar Sovereign AI API – Version {version}"
        },
        "paths": {}
    }
    if output_path:
        with open(output_path, "w") as f:
            json.dump(spec, f, indent=2)
    return spec

def generate_all_versioned_specs():
    versions = ["v1", "v2", "v3"]
    for v in versions:
        generate_versioned_openapi(v, None, f"docs/openapi_{v}.json")
    print("Versioned OpenAPI specs generated")
