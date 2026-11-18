import asyncio
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import AuthUser, current_member
from app.deps import get_catalogue
from app.models.track import Preferences, Track
from app.services.music_catalogue import Catalogue
from app.services.playlist_generator import MIN_TRACKS, generate_set, pick_replacement

router = APIRouter(prefix="/api/playlists", tags=["Playlists"])


async def _candidates(cat: Catalogue, prefs: Preferences, min_pool: int = 120) -> tuple[list[Track], dict]:
    langs = prefs.languages or [None]
    seen: dict[str, Track] = {}
    errors: dict = {}

    # Run primary language/genre searches in parallel for maximum speed
    tasks = []
    for lang in langs:
        genres = prefs.genres.get(lang, []) if lang else []
        if genres:
            tasks.append(cat.search("", language=lang, genres=genres, limit=50, playable_only=True))
        tasks.append(cat.search("", language=lang, genres=None, limit=50, playable_only=True))

    results = await asyncio.gather(*tasks)
    for tracks, errs in results:
        errors.update(errs)
        for t in tracks:
            seen.setdefault(t.id, t)

    # Top up in parallel only if we still have fewer than MIN_TRACKS
    if len(seen) < MIN_TRACKS:
        fallback_tasks = [
            cat.search(q, language=None, genres=None, limit=50, playable_only=True)
            for q in ("bollywood hits", "party songs", "pop hits")
        ]
        fb_results = await asyncio.gather(*fallback_tasks)
        for tracks, errs in fb_results:
            errors.update(errs)
            for t in tracks:
                seen.setdefault(t.id, t)
            if len(seen) >= min_pool:
                break

    return list(seen.values()), errors


class GenerateIn(BaseModel):
    preferences: Preferences
    seed: int | None = None


@router.post("/generate")
async def generate(body: GenerateIn, _: AuthUser = Depends(current_member),
                   cat: Catalogue = Depends(get_catalogue)):
    cands, errors = await _candidates(cat, body.preferences)
    seed = body.seed if body.seed is not None else int(time.time())
    tracks = generate_set(cands, body.preferences, seed=seed)
    return {"tracks": tracks, "errors": errors, "seed": seed, "candidate_count": len(cands)}


class ReplaceIn(BaseModel):
    preferences: Preferences
    current: list[Track] = Field(max_length=300)
    index: int = Field(ge=0)


@router.post("/replace")
async def replace(body: ReplaceIn, _: AuthUser = Depends(current_member),
                  cat: Catalogue = Depends(get_catalogue)):
    if body.index >= len(body.current):
        raise HTTPException(status_code=422, detail="index out of range")
    cands, _errors = await _candidates(cat, body.preferences, min_pool=60)
    t = pick_replacement(cands, body.current, body.index, body.preferences, seed=int(time.time()))
    if not t:
        raise HTTPException(status_code=404, detail="No other playable tracks available")
    return {"track": t}
