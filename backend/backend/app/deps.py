from app.services.music_catalogue import Catalogue

_catalogue: Catalogue | None = None


def get_catalogue() -> Catalogue:
    global _catalogue
    if _catalogue is None:
        _catalogue = Catalogue()
    return _catalogue
