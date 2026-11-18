from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import AuthUser, current_member
from app.database.client import rest

router = APIRouter(prefix="/api/library", tags=["Library"])


class SetIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    preferences: dict[str, Any]
    tracks: list[dict[str, Any]] = Field(max_length=200)
    completed: bool = False
    skipped_count: int = Field(default=0, ge=0)


@router.get("/sets")
async def list_sets(user: AuthUser = Depends(current_member)):
    rows = await rest("GET", "/rest/v1/rove_sets", user.token,
                      params={"select": "*", "order": "created_at.desc", "limit": "100"})
    return {"sets": rows}


@router.post("/sets")
async def create_set(body: SetIn, user: AuthUser = Depends(current_member)):
    rows = await rest("POST", "/rest/v1/rove_sets", user.token, prefer="return=representation",
                      json={**body.model_dump(), "user_id": user.id})
    return rows[0]


@router.get("/sets/{set_id}")
async def get_set(set_id: str, user: AuthUser = Depends(current_member)):
    rows = await rest("GET", "/rest/v1/rove_sets", user.token,
                      params={"select": "*", "id": f"eq.{set_id}", "limit": "1"})
    if not rows:
        raise HTTPException(status_code=404, detail="Set not found")
    return rows[0]


@router.put("/sets/{set_id}")
async def update_set(set_id: str, body: SetIn, user: AuthUser = Depends(current_member)):
    rows = await rest("PATCH", "/rest/v1/rove_sets", user.token, params={"id": f"eq.{set_id}"},
                      prefer="return=representation", json=body.model_dump())
    if not rows:
        raise HTTPException(status_code=404, detail="Set not found")
    return rows[0]


@router.delete("/sets/{set_id}")
async def delete_set(set_id: str, user: AuthUser = Depends(current_member)):
    await rest("DELETE", "/rest/v1/rove_sets", user.token, params={"id": f"eq.{set_id}"})
    return {"deleted": True}


class FavIn(BaseModel):
    track: dict[str, Any]


@router.get("/favorites")
async def list_favorites(user: AuthUser = Depends(current_member)):
    rows = await rest("GET", "/rest/v1/rove_favorites", user.token,
                      params={"select": "track_id,track,created_at", "order": "created_at.desc"})
    return {"favorites": rows}


@router.post("/favorites")
async def add_favorite(body: FavIn, user: AuthUser = Depends(current_member)):
    tid = body.track.get("id")
    if not isinstance(tid, str) or not tid:
        raise HTTPException(status_code=422, detail="track.id required")
    await rest("POST", "/rest/v1/rove_favorites", user.token,
               prefer="resolution=merge-duplicates",
               params={"on_conflict": "user_id,track_id"},
               json={"user_id": user.id, "track_id": tid, "track": body.track})
    return {"favorited": True}


@router.delete("/favorites/{track_id}")
async def remove_favorite(track_id: str, user: AuthUser = Depends(current_member)):
    await rest("DELETE", "/rest/v1/rove_favorites", user.token, params={"track_id": f"eq.{track_id}"})
    return {"favorited": False}


class HistoryIn(BaseModel):
    track: dict[str, Any]
    mode: str = Field(pattern="^(segment|full)$")
    completed: bool = False


@router.get("/recent")
async def recent(user: AuthUser = Depends(current_member)):
    rows = await rest("GET", "/rest/v1/rove_play_history", user.token,
                      params={"select": "*", "order": "played_at.desc", "limit": "50"})
    return {"recent": rows}


@router.post("/recent")
async def log_play(body: HistoryIn, user: AuthUser = Depends(current_member)):
    tid = body.track.get("id")
    if not isinstance(tid, str) or not tid:
        raise HTTPException(status_code=422, detail="track.id required")
    await rest("POST", "/rest/v1/rove_play_history", user.token,
               json={"user_id": user.id, "track_id": tid, "track": body.track,
                     "mode": body.mode, "completed": body.completed})
    return {"logged": True}


class RequestIn(BaseModel):
    text: str = Field(min_length=2, max_length=200)
    language: str | None = Field(default=None, max_length=40)


@router.post("/requests")
async def request_song(body: RequestIn, user: AuthUser = Depends(current_member)):
    """Stores a 'missing song' request. Nothing is fetched or added automatically."""
    await rest("POST", "/rest/v1/rove_song_requests", user.token,
               json={"user_id": user.id, "text": body.text.strip(), "language": body.language})
    return {"requested": True}
