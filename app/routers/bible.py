from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .. import bible
from ..storage import FileStore, get_store

router = APIRouter(prefix="/api/bible", tags=["bible"])


def _check(translation: str) -> str:
    if translation not in bible.TRANSLATIONS:
        raise HTTPException(404, f"Unknown translation '{translation}'")
    return translation


@router.get("/translations")
def translations():
    return bible.translations()


@router.get("/books")
def books(translation: str = "kjv", order: str = Query("canonical", pattern="^(canonical|alpha)$")):
    return bible.books(_check(translation), order)


@router.get("/passage")
def passage(
    translation: str = "kjv",
    ref: str | None = None,
    book: int | None = None,
    chapter: int | None = None,
    start: int | None = None,
    end: int | None = None,
    record: bool = False,
    store: FileStore = Depends(get_store),
):
    """Look up by free-text `ref` ("John 3:16-18") or by `book`/`chapter`/`start`/`end`."""
    _check(translation)
    try:
        if ref:
            result = bible.lookup(translation, ref)
        elif book and chapter:
            result = bible.passage(translation, book, chapter, start, end)
        else:
            raise HTTPException(400, "Provide `ref` or `book` and `chapter`")
    except bible.BibleError as e:
        raise HTTPException(404, str(e))
    if record:
        store.add_history(translation, result["reference"])
    return result


class HistoryIn(BaseModel):
    translation: str
    reference: str


@router.get("/history")
def history(limit: int = Query(50, ge=1, le=500), store: FileStore = Depends(get_store)):
    return store.list_history(limit)


@router.post("/history")
def add_history(item: HistoryIn, store: FileStore = Depends(get_store)):
    return store.add_history(_check(item.translation), item.reference.strip())


@router.delete("/history")
def clear_history(store: FileStore = Depends(get_store)):
    store.clear_history()
    return {"ok": True}
