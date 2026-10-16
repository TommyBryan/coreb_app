import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .base import NotFound, Row

SCHEMA = """
CREATE TABLE IF NOT EXISTS songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL DEFAULT '',
    lyrics TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS slides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bible_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    translation TEXT NOT NULL,
    reference TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    url TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SqliteStore:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)

    def _all(self, sql: str, params: tuple = ()) -> list[Row]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def _one(self, sql: str, params: tuple = ()) -> Row:
        rows = self._all(sql, params)
        if not rows:
            raise NotFound()
        return rows[0]

    def _write(self, sql: str, params: tuple = ()) -> int:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            if cur.rowcount == 0:
                raise NotFound()
            return cur.lastrowid

    # Songs
    def list_songs(self, query: str = "") -> list[Row]:
        if query:
            like = f"%{query}%"
            return self._all(
                "SELECT * FROM songs WHERE title LIKE ? OR author LIKE ? OR lyrics LIKE ? "
                "ORDER BY title COLLATE NOCASE",
                (like, like, like),
            )
        return self._all("SELECT * FROM songs ORDER BY title COLLATE NOCASE")

    def get_song(self, song_id: int) -> Row:
        return self._one("SELECT * FROM songs WHERE id = ?", (song_id,))

    def create_song(self, title: str, author: str, lyrics: str) -> Row:
        now = _now()
        new_id = self._write(
            "INSERT INTO songs (title, author, lyrics, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (title, author, lyrics, now, now),
        )
        return self.get_song(new_id)

    def update_song(self, song_id: int, title: str, author: str, lyrics: str) -> Row:
        self._write(
            "UPDATE songs SET title = ?, author = ?, lyrics = ?, updated_at = ? WHERE id = ?",
            (title, author, lyrics, _now(), song_id),
        )
        return self.get_song(song_id)

    def delete_song(self, song_id: int) -> None:
        self._write("DELETE FROM songs WHERE id = ?", (song_id,))

    def count_songs(self) -> int:
        return self._one("SELECT COUNT(*) AS n FROM songs")["n"]

    # Slides
    def list_slides(self) -> list[Row]:
        return self._all("SELECT * FROM slides ORDER BY updated_at DESC, id DESC")

    def create_slide(self, title: str, body: str) -> Row:
        now = _now()
        new_id = self._write(
            "INSERT INTO slides (title, body, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (title, body, now, now),
        )
        return self._one("SELECT * FROM slides WHERE id = ?", (new_id,))

    def update_slide(self, slide_id: int, title: str, body: str) -> Row:
        self._write(
            "UPDATE slides SET title = ?, body = ?, updated_at = ? WHERE id = ?",
            (title, body, _now(), slide_id),
        )
        return self._one("SELECT * FROM slides WHERE id = ?", (slide_id,))

    def delete_slide(self, slide_id: int) -> None:
        self._write("DELETE FROM slides WHERE id = ?", (slide_id,))

    # Bible history
    def list_history(self, limit: int = 50) -> list[Row]:
        return self._all(
            "SELECT * FROM bible_history ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)
        )

    def add_history(self, translation: str, reference: str) -> Row:
        with self._lock:
            self._conn.execute(
                "DELETE FROM bible_history WHERE translation = ? AND reference = ?",
                (translation, reference),
            )
            self._conn.commit()
        new_id = self._write(
            "INSERT INTO bible_history (translation, reference, created_at) VALUES (?, ?, ?)",
            (translation, reference, _now()),
        )
        return self._one("SELECT * FROM bible_history WHERE id = ?", (new_id,))

    def clear_history(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM bible_history")
            self._conn.commit()

    # Media
    def list_media(self) -> list[Row]:
        return self._all("SELECT * FROM media ORDER BY created_at DESC, id DESC")

    def get_media(self, media_id: int) -> Row:
        return self._one("SELECT * FROM media WHERE id = ?", (media_id,))

    def add_media(self, name: str, kind: str, path: str, url: str) -> Row:
        new_id = self._write(
            "INSERT INTO media (name, kind, path, url, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, kind, path, url, _now()),
        )
        return self.get_media(new_id)

    def delete_media(self, media_id: int) -> Row:
        row = self.get_media(media_id)
        self._write("DELETE FROM media WHERE id = ?", (media_id,))
        return row
