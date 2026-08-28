import base64
import binascii
import secrets

from fastapi import Request
from fastapi.responses import JSONResponse

from .config import AUTH_ENABLED, ROKU_API_KEY, WEB_PASSWORD, WEB_USERNAME


def validate_auth_config() -> None:
    if not AUTH_ENABLED:
        return

    missing = [
        name
        for name, value in (
            ("WEB_USERNAME", WEB_USERNAME),
            ("WEB_PASSWORD", WEB_PASSWORD),
            ("ROKU_API_KEY", ROKU_API_KEY),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "AUTH_ENABLED=true, mas faltam variáveis obrigatórias: " + ", ".join(missing)
        )
    if len(WEB_PASSWORD) < 12:
        raise RuntimeError("WEB_PASSWORD deve ter pelo menos 12 caracteres.")
    if len(ROKU_API_KEY) < 32:
        raise RuntimeError("ROKU_API_KEY deve ter pelo menos 32 caracteres.")


def _basic_credentials(authorization: str | None) -> tuple[str, str] | None:
    if not authorization:
        return None

    scheme, separator, encoded = authorization.partition(" ")
    if not separator or scheme.lower() != "basic":
        return None

    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None

    username, separator, password = decoded.partition(":")
    if not separator:
        return None
    return username, password


def _valid_basic_auth(authorization: str | None) -> bool:
    credentials = _basic_credentials(authorization)
    if credentials is None:
        return False

    username, password = credentials
    username_matches = secrets.compare_digest(username.encode(), WEB_USERNAME.encode())
    password_matches = secrets.compare_digest(password.encode(), WEB_PASSWORD.encode())
    return username_matches and password_matches


def _valid_roku_key(value: str | None) -> bool:
    if not value or not ROKU_API_KEY:
        return False
    return secrets.compare_digest(value.encode(), ROKU_API_KEY.encode())


async def authentication_middleware(request: Request, call_next):
    if not AUTH_ENABLED or request.url.path == "/healthz":
        return await call_next(request)

    is_api = request.url.path == "/api" or request.url.path.startswith("/api/")
    roku_authenticated = is_api and _valid_roku_key(request.headers.get("x-tvdash-key"))
    web_authenticated = _valid_basic_auth(request.headers.get("authorization"))

    if not roku_authenticated and not web_authenticated:
        return JSONResponse(
            status_code=401,
            content={"detail": "Não autorizado"},
            headers={
                "WWW-Authenticate": 'Basic realm="TV Dash"',
                "Cache-Control": "no-store",
            },
        )

    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response
