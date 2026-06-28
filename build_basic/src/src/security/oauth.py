# security/oauth.py – OAuth2/OIDC client stubs for SSO
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
import httpx
import secrets
import os
from urllib.parse import urlencode
from .users import UserManager
from .jwt import create_token

router = APIRouter(prefix="/v1/auth", tags=["authentication"])

# Configuration (load from env)
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
MICROSOFT_CLIENT_ID = os.environ.get("MICROSOFT_CLIENT_ID", "")
MICROSOFT_CLIENT_SECRET = os.environ.get("MICROSOFT_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("OAUTH_REDIRECT_URI", "http://localhost:8080/v1/auth/callback")

# State storage (in production use Redis)
state_store = {}

@router.get("/login/google")
async def google_login():
    state = secrets.token_urlsafe(16)
    state_store[state] = {"provider": "google", "created": time.time()}
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state
    }
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")

@router.get("/login/github")
async def github_login():
    state = secrets.token_urlsafe(16)
    state_store[state] = {"provider": "github", "created": time.time()}
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "user:email",
        "state": state
    }
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{urlencode(params)}")

@router.get("/callback")
async def oauth_callback(code: str, state: str):
    stored = state_store.pop(state, None)
    if not stored:
        raise HTTPException(400, "Invalid state")
    provider = stored["provider"]
    user_info = None
    if provider == "google":
        async with httpx.AsyncClient() as client:
            token_resp = await client.post("https://oauth2.googleapis.com/token", data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "grant_type": "authorization_code"
            })
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            user_resp = await client.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {access_token}"})
            user_info = user_resp.json()
            email = user_info.get("email")
            name = user_info.get("name", email)
    elif provider == "github":
        async with httpx.AsyncClient() as client:
            token_resp = await client.post("https://github.com/login/oauth/access_token", data={
                "code": code,
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI
            }, headers={"Accept": "application/json"})
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            user_resp = await client.get("https://api.github.com/user", headers={"Authorization": f"Bearer {access_token}"})
            user_info = user_resp.json()
            email = user_info.get("email") or f"{user_info['login']}@users.noreply.github.com"
            name = user_info.get("name", user_info["login"])
    
    if not user_info or not email:
        raise HTTPException(400, "Failed to get user info")
    
    # Create or retrieve user in local DB
    um = UserManager()
    user = um.authenticate(email, "")  # special case – would need separate logic
    if not user:
        # Auto-create user
        user_id = um.create_user(email.split('@')[0], email, secrets.token_urlsafe(12), "user")
        user = um.get_user(user_id)
    jwt_token = create_token(user["user_id"], user["username"], user["role"])
    return {"access_token": jwt_token, "token_type": "bearer", "user": user}
