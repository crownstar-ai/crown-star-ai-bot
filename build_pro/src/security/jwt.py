# security/jwt.py – JWT token creation and verification
import jwt
import time
import os
from datetime import datetime, timedelta
from typing import Dict, Optional

JWT_SECRET = os.environ.get("JWT_SECRET", "crownstar-super-secret-change-in-production")
JWT_ALGORITHM = "HS256"

def create_token(user_id: str, username: str, role: str, expires_hours: int = 24) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_hours * 3600
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token: str) -> Optional[Dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def refresh_token(token: str) -> Optional[str]:
    payload = verify_token(token)
    if not payload:
        return None
    # Refresh if within 1 hour of expiry
    exp = payload.get("exp", 0)
    if exp - int(time.time()) < 3600:
        return create_token(payload["sub"], payload["username"], payload["role"])
    return token
