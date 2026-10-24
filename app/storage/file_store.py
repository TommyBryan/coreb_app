"""Plain-file storage: songs in songs.csv, everything else in small JSON files.

All files live in one folder (Settings.user_dir) so they are easy to back up or edit by hand.
"""

import csv
import json
import os
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

Row = dict[str, Any]

SONG_FIELDS = ["id", "title", "author", "lyrics", "created_at", "updated_at"]


class NotFound(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="")
    os.replace(tmp, path)


class FileStore:
    def __init__(self, folder: Path, seed_songs: Path | None = None) -> None:
        self.folder = folder
        self.folder.mkdir(parents=True, exist_ok=True)
        self.songs_path = folder / "songs.csv"
        self._lock = threading.RLock()
        if not self.songs_path.exists():
            if seed_songs and seed_songs.exists():
                self._seed(seed_songs)
            else:
                self._save_songs([])

    # ---- helpers -------------------------------------------------------------------------

    def _seed(self, seed: Path) -> None:
        now = _now()
        with open(seed, newline="", encoding="utf-8-sig") as f:
            rows = [r for r in csv.DictReader(f) if (r.get("title") or "").strip()]
        self._save_songs([
            {"id": i, "title": r["title"].strip(), "author": (r.get("author") or "").strip(),
             "lyrics": (r.get("lyrics") or "").strip(), "created_at": now, "updated_at": now}
            for i, r in enumerate(rows, start=1)
        ])

    def _load_songs(self) -> list[Row]:
        with open(self.songs_path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        songs, next_id = [], 1 + max((int(r["id"]) for r in rows if (r.get("id") or "").isdigit()), default=0)
        for r in rows:
            if not (r.get("title") or "").strip():
                continue
            if not (r.get("id") or "").isdigit():  # a row someone added by hand
                r["id"], next_id = str(next_id), next_id + 1
            songs.append({k: (r.get(k) or "") for k in SONG_FIELDS} | {"id": int(r["id"])})
        return songs

    def _save_songs(self, songs: list[Row]) -> None:
        tmp = self.songs_path.with_suffix(".csv.tmp")
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=SONG_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(songs)
        os.replace(tmp, self.songs_path)

    def _load_json(self, name: str) -> list[Row]:
        path = self.folder / f"{name}.json"
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            shutil.copy(path, path.with_suffix(".json.broken"))
            return []
        return data if isinstance(data, list) else []

    def _save_json(self, name: str, rows: list[Row]) -> None:
        _atomic_write(self.folder / f"{name}.json", json.dumps(rows, ensure_ascii=False, indent=2))

    @staticmethod
    def _next_id(rows: list[Row]) -> int:
        return 1 + max((r["id"] for r in rows), default=0)

    @staticmethod
    def _find(rows: list[Row], row_id: int) -> Row:
        for r in rows:
            if r["id"] == row_id:
                return r
        raise NotFound()

    # ---- songs (songs.csv) ---------------------------------------------------------------

    def list_songs(self, query: str = "") -> list[Row]:
        with self._lock:
            songs = self._load_songs()
        if query:
            q = query.casefold()
            songs = [s for s in songs if q in s["title"].casefold()
                     or q in s["author"].casefold() or q in s["lyrics"].casefold()]
        return sorted(songs, key=lambda s: s["title"].casefold())

    def get_song(self, song_id: int) -> Row:
        with self._lock:
            return self._find(self._load_songs(), song_id)

    def create_song(self, title: str, author: str, lyrics: str) -> Row:
        with self._lock:
            songs = self._load_songs()
            now = _now()
            song = {"id": self._next_id(songs), "title": title, "author": author,
                    "lyrics": lyrics, "created_at": now, "updated_at": now}
            self._save_songs(songs + [song])
            return song

    def update_song(self, song_id: int, title: str, author: str, lyrics: str) -> Row:
        with self._lock:
            songs = self._load_songs()
            song = self._find(songs, song_id)
            song.update(title=title, author=author, lyrics=lyrics, updated_at=_now())
            self._save_songs(songs)
            return song

    def delete_song(self, song_id: int) -> None:
        with self._lock:
            songs = self._load_songs()
            self._find(songs, song_id)
            self._save_songs([s for s in songs if s["id"] != song_id])

    # ---- slides (slides.json) ------------------------------------------------------------

    def list_slides(self) -> list[Row]:
        with self._lock:
            return sorted(self._load_json("slides"), key=lambda r: (r["updated_at"], r["id"]), reverse=True)

    def create_slide(self, title: str, body: str) -> Row:
        with self._lock:
            rows = self._load_json("slides")
            now = _now()
            row = {"id": self._next_id(rows), "title": title, "body": body, "created_at": now, "updated_at": now}
            self._save_json("slides", rows + [row])
            return row

    def update_slide(self, slide_id: int, title: str, body: str) -> Row:
        with self._lock:
            rows = self._load_json("slides")
            row = self._find(rows, slide_id)
            row.update(title=title, body=body, updated_at=_now())
            self._save_json("slides", rows)
            return row

    def delete_slide(self, slide_id: int) -> None:
        with self._lock:
            rows = self._load_json("slides")
            self._find(rows, slide_id)
            self._save_json("slides", [r for r in rows if r["id"] != slide_id])

    # ---- bible history (history.json, newest first, capped) ------------------------------

    HISTORY_MAX = 200

    def list_history(self, limit: int = 50) -> list[Row]:
        with self._lock:
            return self._load_json("history")[:limit]

    def add_history(self, translation: str, reference: str) -> Row:
        with self._lock:
            existing = self._load_json("history")
            rows = [r for r in existing
                    if not (r["translation"] == translation and r["reference"] == reference)]
            row = {"id": self._next_id(existing), "translation": translation,
                   "reference": reference, "created_at": _now()}
            self._save_json("history", ([row] + rows)[: self.HISTORY_MAX])
            return row

    def clear_history(self) -> None:
        with self._lock:
            self._save_json("history", [])

    # ---- media metadata (media.json; files live in media/) -------------------------------

    def list_media(self) -> list[Row]:
        with self._lock:
            return list(reversed(self._load_json("media")))

    def get_media(self, media_id: int) -> Row:
        with self._lock:
            return self._find(self._load_json("media"), media_id)

    def add_media(self, name: str, kind: str, path: str, url: str) -> Row:
        with self._lock:
            rows = self._load_json("media")
            row = {"id": self._next_id(rows), "name": name, "kind": kind, "path": path,
                   "url": url, "created_at": _now()}
            self._save_json("media", rows + [row])
            return row

    def delete_media(self, media_id: int) -> Row:
        with self._lock:
            rows = self._load_json("media")
            row = self._find(rows, media_id)
            self._save_json("media", [r for r in rows if r["id"] != media_id])
            return row
