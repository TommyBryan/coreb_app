import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from ..config import Settings, get_settings
from ..storage import FileStore, NotFound, get_store

router = APIRouter(prefix="/api/media", tags=["media"])

KINDS = {
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image", ".gif": "image",
    ".mp4": "video", ".webm": "video",
}
MAX_BYTES = 500 * 1024 * 1024
CHUNK = 1024 * 1024


def kind_for(filename: str) -> tuple[str, str]:
    ext = Path(filename or "").suffix.lower()
    if ext not in KINDS:
        raise HTTPException(400, f"Unsupported file type '{ext or filename}'. Use: {', '.join(KINDS)}")
    return ext, KINDS[ext]


@router.get("")
def list_media(store: FileStore = Depends(get_store)):
    return store.list_media()


@router.post("", status_code=201)
async def upload(
    file: UploadFile,
    store: FileStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
):
    ext, kind = kind_for(file.filename)
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{ext}"
    dest = settings.media_dir / stored
    size = 0
    with open(dest, "wb") as out:
        while chunk := await file.read(CHUNK):
            size += len(chunk)
            if size > MAX_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "File is larger than 500 MB")
            out.write(chunk)
    name = Path(file.filename).stem[:120] or "media"
    return store.add_media(name, kind, stored, f"/media-files/{stored}")


@router.delete("/{media_id}")
def delete_media(media_id: int, store: FileStore = Depends(get_store), settings: Settings = Depends(get_settings)):
    try:
        row = store.delete_media(media_id)
    except NotFound:
        raise HTTPException(404, "Media not found")
    (settings.media_dir / Path(row["path"]).name).unlink(missing_ok=True)
    return {"ok": True}
