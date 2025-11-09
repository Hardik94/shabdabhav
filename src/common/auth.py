from fastapi import Request, HTTPException
from .config import get_env


def get_allowed_tokens() -> set[str]:
    raw = get_env("API_TOKENS", "") or ""
    return {tok.strip() for tok in raw.split(",") if tok.strip()}


async def require_auth(request: Request) -> None:
    allowed = get_allowed_tokens()
    if not allowed:
        return
    token = request.headers.get("Authorization")
    if token:
        token = token.replace("Bearer ", "").strip()
    if not (token and token in allowed):
        raise HTTPException(status_code=401, detail="Unauthorized")


