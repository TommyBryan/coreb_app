"""Bible lookups backed by the read-only CSVs in data/bible/."""

import csv
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache

from .config import get_settings

TRANSLATIONS = {
    "kjv": {"id": "kjv", "name": "King James Version", "short": "KJV", "lang": "en", "file": "kjv.csv"},
    "rv1909": {"id": "rv1909", "name": "Reina-Valera 1909", "short": "RV1909", "lang": "es", "file": "rv1909.csv"},
}

# Common short forms people type that aren't plain prefixes of a book name.
ABBREVIATIONS = {
    "gn": 1, "ex": 2, "lv": 3, "nm": 4, "dt": 5, "jos": 6, "jue": 7, "jdg": 7,
    "1sm": 9, "2sm": 10, "1kgs": 11, "2kgs": 12, "1r": 11, "2r": 12,
    "ps": 19, "psa": 19, "sal": 19, "pr": 20, "prv": 20, "ec": 21, "ecl": 21,
    "sos": 22, "song": 22, "ct": 22, "is": 23, "jr": 24, "lm": 25, "ez": 26,
    "dn": 27, "os": 28, "jl": 29, "am": 30, "abd": 31, "jon": 32, "mi": 33,
    "mt": 40, "mk": 41, "mr": 41, "lk": 42, "lc": 42, "jn": 43, "jhn": 43,
    "ac": 44, "hch": 44, "rm": 45, "ro": 45, "1co": 46, "2co": 47, "ga": 48,
    "ep": 49, "php": 50, "phil": 50, "flp": 50, "fil": 50, "col": 51, "1ts": 52, "2ts": 53, "1th": 52,
    "2th": 53, "1tm": 54, "2tm": 55, "tit": 56, "phm": 57, "flm": 57, "heb": 58,
    "jas": 59, "stg": 59, "1pe": 60, "2pe": 61, "1jn": 62, "2jn": 63, "3jn": 64,
    "jud": 65, "rev": 66, "rv": 66, "ap": 66, "apoc": 66,
}

_ORDINALS = {"iii": "3", "ii": "2", "i": "1", "first": "1", "second": "2", "third": "3",
             "primera": "1", "segunda": "2", "tercera": "3", "primero": "1", "segundo": "2"}

REF_RE = re.compile(r"^\s*(?P<book>.+?)\s*(?P<chapter>\d+)\s*(?:[:.,]\s*(?P<start>\d+)\s*(?:[-–]\s*(?P<end>\d+))?)?\s*$")


class BibleError(ValueError):
    pass


@dataclass
class Book:
    order: int
    name: str
    chapters: int = 0


@dataclass
class Translation:
    id: str
    books: list[Book] = field(default_factory=list)
    verses: dict[tuple[int, int], list[tuple[int, str]]] = field(default_factory=dict)

    def book(self, order: int) -> Book:
        for b in self.books:
            if b.order == order:
                return b
        raise BibleError(f"Unknown book #{order}")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = text.replace(".", " ")
    parts = text.split()
    if parts and parts[0] in _ORDINALS:
        parts[0] = _ORDINALS[parts[0]]
    return "".join(parts)


def _alpha_key(name: str) -> tuple[str, str]:
    m = re.match(r"^(\d)\s+(.*)$", name)
    if m:
        return normalize(m.group(2)), m.group(1)
    return normalize(name), ""


@lru_cache(maxsize=None)
def load(translation_id: str) -> Translation:
    meta = TRANSLATIONS.get(translation_id)
    if not meta:
        raise BibleError(f"Unknown translation '{translation_id}'")
    path = get_settings().data_dir / "bible" / meta["file"]
    tr = Translation(id=translation_id)
    by_order: dict[int, Book] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            order, chapter, verse = int(row["book_order"]), int(row["chapter"]), int(row["verse"])
            book = by_order.get(order)
            if book is None:
                book = by_order[order] = Book(order=order, name=row["book"])
                tr.books.append(book)
            book.chapters = max(book.chapters, chapter)
            tr.verses.setdefault((order, chapter), []).append((verse, row["text"]))
    return tr


def translations() -> list[dict]:
    return [{k: v for k, v in meta.items() if k != "file"} for meta in TRANSLATIONS.values()]


def books(translation_id: str, order: str = "canonical") -> list[dict]:
    items = list(load(translation_id).books)
    if order == "alpha":
        items.sort(key=lambda b: _alpha_key(b.name))
    return [{"order": b.order, "name": b.name, "chapters": b.chapters} for b in items]


def chapter_verses(translation_id: str, book_order: int, chapter: int) -> list[tuple[int, str]]:
    tr = load(translation_id)
    verses = tr.verses.get((book_order, chapter))
    if not verses:
        raise BibleError(f"{tr.book(book_order).name} has no chapter {chapter}")
    return verses


@lru_cache(maxsize=1)
def _aliases() -> dict[str, int]:
    names: dict[str, int] = {}
    for tid in TRANSLATIONS:
        for b in load(tid).books:
            names[normalize(b.name)] = b.order
    names["revelationofjohn"] = 66
    names["cantaresdecantares"] = 22
    return names


def find_book(text: str) -> int:
    key = normalize(text)
    if not key:
        raise BibleError("Missing book name")
    aliases = _aliases()
    if key in aliases:
        return aliases[key]
    if key in ABBREVIATIONS:
        return ABBREVIATIONS[key]
    matches = {order for name, order in aliases.items() if name.startswith(key)}
    if len(matches) == 1:
        return matches.pop()
    if not matches:
        raise BibleError(f"Book not found: '{text.strip()}'")
    raise BibleError(f"'{text.strip()}' matches more than one book")


def parse_reference(ref: str) -> tuple[int, int, int | None, int | None]:
    """'Juan 3:16-18' -> (43, 3, 16, 18). Verse parts are None for a whole chapter."""
    m = REF_RE.match(ref or "")
    if not m:
        raise BibleError(f"Could not read reference '{ref}'")
    start = int(m["start"]) if m["start"] else None
    end = int(m["end"]) if m["end"] else start
    if start is not None and end is not None and end < start:
        start, end = end, start
    return find_book(m["book"]), int(m["chapter"]), start, end


def format_reference(book_name: str, chapter: int, start: int | None, end: int | None) -> str:
    if start is None:
        return f"{book_name} {chapter}"
    if end is None or end == start:
        return f"{book_name} {chapter}:{start}"
    return f"{book_name} {chapter}:{start}-{end}"


def passage(translation_id: str, book_order: int, chapter: int,
            start: int | None = None, end: int | None = None) -> dict:
    tr = load(translation_id)
    book = tr.book(book_order)
    verses = chapter_verses(translation_id, book_order, chapter)
    if start is not None:
        end = end if end is not None else start
        verses = [(n, t) for n, t in verses if start <= n <= end]
        if not verses:
            raise BibleError(f"{book.name} {chapter} has no verse {start}")
    return {
        "translation": translation_id,
        "translation_short": TRANSLATIONS[translation_id]["short"],
        "book": book.name,
        "book_order": book.order,
        "chapter": chapter,
        "chapters": book.chapters,
        "start": start,
        "end": end,
        "reference": format_reference(book.name, chapter, start, end),
        "verses": [{"verse": n, "text": t} for n, t in verses],
    }


def lookup(translation_id: str, ref: str) -> dict:
    book_order, chapter, start, end = parse_reference(ref)
    return passage(translation_id, book_order, chapter, start, end)
