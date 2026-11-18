from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.audio_engine.transitions import plan_transition
from app.core.security import AuthUser, current_member
from app.deps import get_catalogue
from app.services.audio_analysis import AnalysisError, analyse_url
from app.services.music_catalogue import Catalogue
from app.services.playback_manager import authorize

router = APIRouter(prefix="/api", tags=["Playback"])


class TrackRef(BaseModel):
    track_id: str = Field(min_length=3, max_length=200)


@router.post("/playback/authorize")
async def playback_authorize(body: TrackRef, _: AuthUser = Depends(current_member),
                             cat: Catalogue = Depends(get_catalogue)):
    t = await cat.get_track(body.track_id)
    if not t:
        # Unknown tracks are denied, not guessed.
        return {"track_id": body.track_id, "playable": False, "audio_url": None, "source": None,
                "allowed": {"full": False, "segment": False, "seek": False, "crossfade": False},
                "default_mode": "denied", "reason": "Track not found at provider", "license": None}
    return authorize(t)


class TransitionIn(BaseModel):
    from_track_id: str
    to_track_id: str


@router.post("/playback/transition")
async def transition(body: TransitionIn, _: AuthUser = Depends(current_member),
                     cat: Catalogue = Depends(get_catalogue)):
    a, b = await cat.get_track(body.from_track_id), await cat.get_track(body.to_track_id)
    if not a or not b:
        raise HTTPException(status_code=404, detail="Track not found")
    return plan_transition(a, b)


@router.post("/audio/analyze")
async def analyze(body: TrackRef, _: AuthUser = Depends(current_member),
                  cat: Catalogue = Depends(get_catalogue)):
    """Analyses a track's audio (BPM, key, estimated highlight, waveform).
    Only tracks the provider licenses for full playback are fetched."""
    t = await cat.get_track(body.track_id)
    if not t or not authorize(t)["playable"]:
        raise HTTPException(status_code=403, detail="Track is not available for analysis")
    if not t.audio_url:
        raise HTTPException(status_code=422, detail="Audio analysis is not available for YouTube tracks")
    try:
        return {"track_id": t.id, **await analyse_url(t.audio_url)}
    except AnalysisError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
