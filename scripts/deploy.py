# scripts/deploy.py
"""
Production deployment script.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def run_command(cmd, env=None):
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        print("ERROR:", result.stderr)
        sys.exit(1)
    print(result.stdout)
    return result.stdout


def deploy():
    parser = argparse.ArgumentParser(description="Deploy CrownStar")
    parser.add_argument("--env", default=".env.prod", help="Environment file")
    parser.add_argument("--port", default=8000, type=int, help="Port")
    parser.add_argument("--workers", default=4, type=int, help="Number of workers")
    parser.add_argument("--skip-migrations", action="store_true", help="Skip migrations")
    args = parser.parse_args()
    
    # Set environment
    if os.path.exists(args.env):
        with open(args.env) as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    key, val = line.strip().split("=", 1)
                    os.environ[key] = val
    
    # Install dependencies
    run_command("pip install -r requirements.txt")
    
    # Run migrations
    if not args.skip_migrations:
        run_command("python -m src.database.migrations")
    
    # Start server
    cmd = f"uvicorn src.server.app:app --host 0.0.0.0 --port {args.port} --workers {args.workers}"
    print(f"Starting server: {cmd}")
    os.execvp("uvicorn", ["uvicorn", "src.server.app:app", "--host", "0.0.0.0", "--port", str(args.port), "--workers", str(args.workers)])


if __name__ == "__main__":
    deploy()
