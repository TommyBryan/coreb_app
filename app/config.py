import os
import sys
from functools import lru_cache
from pathlib import Path


def _resource_root() -> Path:
    """Folder holding the bundled `static/` and `data/` (PyInstaller unpacks to _MEIPASS)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent.parent


def _default_user_dir() -> Path:
    """Writable folder for songs.csv, the JSON files and uploaded media."""
    if os.environ.get("VERCEL"):
        return Path("/tmp/coreb")  # Vercel's only writable disk; wiped between cold starts
    if getattr(sys, "frozen", False):
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "COREB"
    return _resource_root() / "var"


class Settings:
    def __init__(self) -> None:
        root = _resource_root()
        self.static_dir = root / "static"
        self.data_dir = root / "data"
        self.user_dir = Path(os.environ.get("COREB_DATA_DIR") or _default_user_dir())
        self.media_dir = self.user_dir / "media"


@lru_cache
def get_settings() -> Settings:
    return Settings()
