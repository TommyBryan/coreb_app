from functools import lru_cache

from ..config import get_settings
from .base import NotFound, Store
from .sqlite_store import SqliteStore

__all__ = ["NotFound", "Store", "SqliteStore", "get_store"]


@lru_cache
def get_store() -> Store:
    settings = get_settings()
    if settings.use_supabase:
        from .supabase_store import SupabaseStore

        return SupabaseStore(settings.supabase_url, settings.supabase_key, settings.supabase_bucket)
    return SqliteStore(settings.db_path)
