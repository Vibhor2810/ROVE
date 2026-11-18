from __future__ import annotations

import asyncio
import logging

from app.core.permissions import TrackPermission, permission_allowed
from app.models.track import Track
from app.music_providers import MusicProvider, ProviderError, default_providers

log = logging.getLogger("rove.catalogue")


def is_playable(t: Track) -> bool:
    return bool(t.audio_url or t.youtube_id) and permission_allowed(t.rights.model_dump(), TrackPermission.FULL_PLAYBACK)


class Catalogue:
    def __init__(self, providers: list[MusicProvider] | None = None):
        self.providers = providers if providers is not None else default_providers()

    def by_name(self, name: str) -> MusicProvider | None:
        return next((p for p in self.providers if p.name == name), None)

    def statuses(self) -> list[dict]:
        return [p.status() for p in self.providers]

    async def search(self, query="", *, language=None, genres=None, limit=20,
                     playable_only=False) -> tuple[list[Track], dict[str, str]]:
        """Returns (tracks, errors_by_provider). A failing provider never sinks the rest."""
        active = [p for p in self.providers if p.configured()]

        async def run(p: MusicProvider):
            try:
                return p.name, await p.search(query, language=language, genres=genres, limit=limit), None
            except ProviderError as exc:
                log.warning("provider %s failed: %s", p.name, exc)
                return p.name, [], str(exc)

        results = await asyncio.gather(*(run(p) for p in active))
        tracks: list[Track] = []
        errors: dict[str, str] = {}
        seen: set[str] = set()
        for name, items, err in results:
            if err:
                errors[name] = err
            for t in items:
                if t.id in seen or (playable_only and not is_playable(t)):
                    continue
                seen.add(t.id)
                tracks.append(t)
        return tracks, errors

    async def get_track(self, track_id: str) -> Track | None:
        provider_name, _, pid = track_id.partition(":")
        p = self.by_name(provider_name)
        if not p or not p.configured() or not pid:
            return None
        try:
            return await p.get_track(pid)
        except ProviderError:
            return None
