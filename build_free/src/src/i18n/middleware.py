# i18n/middleware.py – FastAPI middleware for Accept-Language header
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from .service import i18n

class I18nMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Check Accept-Language header
        accept_language = request.headers.get("Accept-Language", "")
        if accept_language:
            # Parse first language code (e.g., "zh-CN,zh;q=0.9" -> "zh")
            lang_code = accept_language.split(",")[0].split("-")[0].lower()
            if lang_code in i18n.get_available_languages():
                i18n.set_language(lang_code)
        # Also check query parameter ?lang=
        lang_param = request.query_params.get("lang")
        if lang_param and lang_param in i18n.get_available_languages():
            i18n.set_language(lang_param)
        response = await call_next(request)
        # Add Content-Language header
        response.headers["Content-Language"] = i18n.get_language()
        return response
