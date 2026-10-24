from functools import lru_cache

from ..config import get_settings
from .file_store import FileStore, NotFound

__all__ = ["FileStore", "NotFound", "get_store"]


@lru_cache
def get_store() -> FileStore:
    settings = get_settings()
    return FileStore(settings.user_dir, seed_songs=settings.data_dir / "songs.csv")
