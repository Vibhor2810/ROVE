"""Open access mode: authentication and invite gating disabled."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Header


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str | None
    token: str
    claims: dict[str, Any]


_GUEST_USER = AuthUser(
    id="00000000-0000-0000-0000-000000000001",
    email="guest@rove.local",
    token="",
    claims={"sub": "00000000-0000-0000-0000-000000000001", "role": "authenticated"},
)


async def get_bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization:
        return ""
    _, _, token = authorization.partition(" ")
    return token


def verify_token(token: str) -> AuthUser:
    return _GUEST_USER


async def current_user(token: str = Depends(get_bearer_token)) -> AuthUser:
    return _GUEST_USER


async def current_member(user: AuthUser = Depends(current_user)) -> AuthUser:
    return user
