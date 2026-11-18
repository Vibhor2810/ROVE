import time

from fastapi import APIRouter, Depends, Query

from app.core.security import AuthUser, current_member
from app.deps import get_catalogue
from app.services.music_catalogue import Catalogue

router = APIRouter(prefix="/api/music", tags=["Music"])

LANGUAGES = ["Hindi", "Punjabi", "English", "Tamil / Telugu", "Garba / Gujarati"]
_cache: dict = {"at": 0.0, "data": None}
_TTL = 600


@router.get("/providers")
async def providers(_: AuthUser = Depends(current_member), cat: Catalogue = Depends(get_catalogue)):
    return {"providers": cat.statuses()}


@router.get("/search")
async def search(q: str = Query("", max_length=100), limit: int = Query(20, ge=1, le=50),
                 playable_only: bool = False, _: AuthUser = Depends(current_member),
                 cat: Catalogue = Depends(get_catalogue)):
    tracks, errors = await cat.search(q, limit=limit, playable_only=playable_only)
    return {"tracks": tracks, "errors": errors}


@router.get("/languages")
async def languages(_: AuthUser = Depends(current_member), cat: Catalogue = Depends(get_catalogue)):
    """Real playable-track counts per language from the live catalogue.
    The count is capped at the page size, flagged via `capped`."""
    # An open catalogue (YouTube) has no meaningful per-language count and each probe would
    # burn search quota, so report "open" instead of inventing a number.
    if any(p.open_catalogue and p.configured() for p in cat.providers):
        return {"languages": [{"language": l, "count": None, "open": True, "capped": False} for l in LANGUAGES], "errors": {}}
    now = time.monotonic()
    if _cache["data"] is not None and now - _cache["at"] < _TTL:
        return _cache["data"]
    out, errors = [], {}
    for lang in LANGUAGES:
        tracks, errs = await cat.search("", language=lang, limit=50, playable_only=True)
        errors.update(errs)
        out.append({"language": lang, "count": len(tracks), "capped": len(tracks) >= 50})
    data = {"languages": out, "errors": errors}
    if not errors:
        _cache.update(at=now, data=data)
    return data
