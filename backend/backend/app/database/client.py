"""Supabase PostgREST access using the CALLER'S JWT, so Row Level Security
applies to every query. The service-role key is not used here."""
from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings

log = logging.getLogger("rove.db")


def _headers(token: str | None) -> dict[str, str]:
    return {
        "apikey": settings.SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {token or settings.SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
    }


def _require_config() -> None:
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        raise HTTPException(status_code=503, detail="Supabase is not configured on the server")


async def rest(method: str, path: str, token: str | None, *, params: dict | None = None,
               json: Any = None, prefer: str | None = None) -> Any:
    _require_config()
    headers = _headers(token)
    if prefer:
        headers["Prefer"] = prefer
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.request(method, f"{settings.SUPABASE_URL}{path}", params=params,
                                json=json, headers=headers)
    except httpx.HTTPError as exc:
        log.error("supabase unreachable: %s", exc)
        raise HTTPException(status_code=502, detail="Database unreachable") from exc
    if r.status_code >= 400:
        log.warning("supabase %s %s -> %s %s", method, path, r.status_code, r.text[:200])
        code = 403 if r.status_code in (401, 403) else (404 if r.status_code == 404 else 400)
        raise HTTPException(status_code=code, detail="Database request rejected")
    return r.json() if r.content else None


async def is_member(user) -> bool:
    rows = await rest("GET", "/rest/v1/rove_members", user.token,
                      params={"select": "user_id", "user_id": f"eq.{user.id}", "limit": "1"})
    return bool(rows)


async def rpc(name: str, token: str | None, args: dict) -> Any:
    return await rest("POST", f"/rest/v1/rpc/{name}", token, json=args)
