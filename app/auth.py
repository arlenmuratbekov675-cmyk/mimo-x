"""Optional API-key auth. Enabled only when settings.api_key is non-empty.

ByteByteGo principle: verify tokens on every call. Disabled by default so
existing open setups keep working until a key is configured.
"""
from fastapi import Header, HTTPException, status

from app.config import settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not settings.api_key:
        return  # auth disabled
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key",
        )
