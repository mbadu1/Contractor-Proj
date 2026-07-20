"""API-key middleware stub for RevWatch."""

from __future__ import annotations

import os

from fastapi import Header, HTTPException, status

# Stub: set REVWATCH_API_KEY to enforce; empty/unset = open (local demo mode)
API_KEY_ENV = "REVWATCH_API_KEY"
API_KEY_HEADER = "X-API-Key"


async def require_api_key(x_api_key: str | None = Header(default=None, alias=API_KEY_HEADER)) -> str | None:
    """
    API-key gate stub.

    - If REVWATCH_API_KEY is unset/empty: allow all requests (dev/demo).
    - If set: require matching X-API-Key header.
    """
    expected = os.environ.get(API_KEY_ENV, "").strip()
    if not expected:
        return None
    if not x_api_key or x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key
