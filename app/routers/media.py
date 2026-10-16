import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ..config import Settings, get_settings
from ..storage import NotFound, Store, get_store

router = APIRouter(prefix="/api/media", tags=["media"])

KINDS = {
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image", ".gif": "image",
    ".mp4": "video", ".webm": "video",
}
MAX_LOCAL_BYTES = 500 * 1024 * 1024
CHUNK = 1024 * 1024


def kind_for(filename: str) -> tuple[str, str]:
    ext = Path(filename or "").suffix.lower()
    if ext not in KINDS:
        raise HTTPException(400, f"Unsupported file type '{ext or filename}'. Use: {', '.join(KINDS)}")
    return ext, KINDS[ext]


def _display_name(filename: str) -> str:
    return Path(filename).stem[:120] or "media"


@router.get("")
def list_media(store: Store = Depends(get_store)):
    return store.list_media()


@router.post("", status_code=201)
async def upload_local(
    file: UploadFile,
    store: Store = Depends(get_store),
    settings: Settings = Depends(get_settings),
):
    """Offline mode: the file is saved next to the SQLite database."""
    if settings.use_supabase:
        raise HTTPException(400, "Online mode uploads go through /api/media/sign")
    ext, kind = kind_for(file.filename)
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{ext}"
    dest = settings.media_dir / stored
    size = 0
    with open(dest, "wb") as out:
        while chunk := await file.read(CHUNK):
            size += len(chunk)
            if size > MAX_LOCAL_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "File is larger than 500 MB")
            out.write(chunk)
    return store.add_media(_display_name(file.filename), kind, stored, f"/media-files/{stored}")


class SignIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)


@router.post("/sign")
def sign_upload(body: SignIn, store: Store = Depends(get_store), settings: Settings = Depends(get_settings)):
    """Online mode, step 1: get a signed URL so the browser uploads straight to Supabase Storage
    (Vercel functions reject request bodies over 4.5 MB)."""
    if not settings.use_supabase:
        raise HTTPException(400, "Signed uploads are only used in online (Supabase) mode")
    ext, _ = kind_for(body.filename)
    return store.signed_upload(f"{uuid.uuid4().hex}{ext}")


class RegisterIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    path: str = Field(pattern=r"^[0-9a-f]{32}\.[a-z0-9]+$")


@router.post("/register", status_code=201)
def register_upload(body: RegisterIn, store: Store = Depends(get_store), settings: Settings = Depends(get_settings)):
    """Online mode, step 2: record the uploaded object once the browser finished the upload."""
    if not settings.use_supabase:
        raise HTTPException(400, "Only used in online (Supabase) mode")
    _, kind = kind_for(body.filename)
    return store.add_media(_display_name(body.filename), kind, body.path, store.public_url(body.path))


@router.delete("/{media_id}")
def delete_media(media_id: int, store: Store = Depends(get_store), settings: Settings = Depends(get_settings)):
    try:
        row = store.delete_media(media_id)
    except NotFound:
        raise HTTPException(404, "Media not found")
    if settings.use_supabase:
        store.remove_object(row["path"])
    else:
        (settings.media_dir / Path(row["path"]).name).unlink(missing_ok=True)
    return {"ok": True}
