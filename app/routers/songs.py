from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .. import songs
from ..storage import FileStore, NotFound, get_store

router = APIRouter(prefix="/api/songs", tags=["songs"])


class SongIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    author: str = Field("", max_length=200)
    lyrics: str = Field("", max_length=50_000)


def _with_sections(song: dict) -> dict:
    return {**song, "sections": songs.split_sections(song.get("lyrics", ""))}


@router.get("")
def list_songs(q: str = "", store: FileStore = Depends(get_store)):
    return store.list_songs(q.strip())


@router.get("/export.csv")
def export_songs(store: FileStore = Depends(get_store)):
    return Response(
        songs.export_csv(store.list_songs()),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="songs.csv"'},
    )


@router.post("/import")
async def import_songs(file: UploadFile, store: FileStore = Depends(get_store)):
    raw = await file.read()
    try:
        count = songs.import_csv(store, raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as e:
        raise HTTPException(400, str(e))
    return {"imported": count}


@router.get("/{song_id}")
def get_song(song_id: int, store: FileStore = Depends(get_store)):
    try:
        return _with_sections(store.get_song(song_id))
    except NotFound:
        raise HTTPException(404, "Song not found")


@router.post("", status_code=201)
def create_song(song: SongIn, store: FileStore = Depends(get_store)):
    return _with_sections(store.create_song(song.title.strip(), song.author.strip(), song.lyrics.strip()))


@router.put("/{song_id}")
def update_song(song_id: int, song: SongIn, store: FileStore = Depends(get_store)):
    try:
        return _with_sections(
            store.update_song(song_id, song.title.strip(), song.author.strip(), song.lyrics.strip())
        )
    except NotFound:
        raise HTTPException(404, "Song not found")


@router.delete("/{song_id}")
def delete_song(song_id: int, store: FileStore = Depends(get_store)):
    try:
        store.delete_song(song_id)
    except NotFound:
        raise HTTPException(404, "Song not found")
    return {"ok": True}
