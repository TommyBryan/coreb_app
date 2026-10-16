"""Song helpers: CSV seed/import/export and splitting lyrics into projectable sections."""

import csv
import io
import re
from pathlib import Path

from .storage.base import Store

CSV_FIELDS = ["title", "author", "lyrics"]


def split_sections(lyrics: str) -> list[str]:
    """A blank line starts a new slide."""
    text = (lyrics or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []
    return [s.strip() for s in re.split(r"\n\s*\n", text) if s.strip()]


def read_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "title" not in [f.strip().lower() for f in reader.fieldnames]:
        raise ValueError("CSV must have a 'title' column (plus optional 'author' and 'lyrics')")
    songs = []
    for row in reader:
        row = {(k or "").strip().lower(): (v or "") for k, v in row.items()}
        title = row.get("title", "").strip()
        if title:
            songs.append({"title": title, "author": row.get("author", "").strip(),
                          "lyrics": row.get("lyrics", "").strip()})
    return songs


def import_csv(store: Store, text: str) -> int:
    songs = read_csv(text)
    for s in songs:
        store.create_song(s["title"], s["author"], s["lyrics"])
    return len(songs)


def export_csv(songs: list[dict]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=CSV_FIELDS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for s in songs:
        writer.writerow(s)
    return out.getvalue()


def seed_if_empty(store: Store, seed_file: Path) -> int:
    if store.count_songs() > 0 or not seed_file.exists():
        return 0
    return import_csv(store, seed_file.read_text(encoding="utf-8"))
