from datetime import datetime, timezone
from typing import Any

from .base import NotFound, Row


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SupabaseStore:
    """Store backed by Supabase Postgres tables (see supabase/migrations) and a Storage bucket."""

    def __init__(self, url: str, key: str, bucket: str = "media", client: Any = None) -> None:
        if client is None:
            from supabase import create_client

            client = create_client(url, key)
        self.client = client
        self.bucket = bucket

    def _table(self, name: str):
        return self.client.table(name)

    @staticmethod
    def _first(resp) -> Row:
        if not resp.data:
            raise NotFound()
        return resp.data[0]

    # Songs
    def list_songs(self, query: str = "") -> list[Row]:
        q = self._table("songs").select("*")
        if query:
            safe = query.replace(",", " ").replace("(", " ").replace(")", " ")
            q = q.or_(f"title.ilike.%{safe}%,author.ilike.%{safe}%,lyrics.ilike.%{safe}%")
        return q.order("title").execute().data

    def get_song(self, song_id: int) -> Row:
        return self._first(self._table("songs").select("*").eq("id", song_id).execute())

    def create_song(self, title: str, author: str, lyrics: str) -> Row:
        now = _now()
        return self._first(self._table("songs").insert(
            {"title": title, "author": author, "lyrics": lyrics, "created_at": now, "updated_at": now}
        ).execute())

    def update_song(self, song_id: int, title: str, author: str, lyrics: str) -> Row:
        return self._first(self._table("songs").update(
            {"title": title, "author": author, "lyrics": lyrics, "updated_at": _now()}
        ).eq("id", song_id).execute())

    def delete_song(self, song_id: int) -> None:
        self._first(self._table("songs").delete().eq("id", song_id).execute())

    def count_songs(self) -> int:
        return self._table("songs").select("id", count="exact").limit(1).execute().count or 0

    # Slides
    def list_slides(self) -> list[Row]:
        return self._table("slides").select("*").order("updated_at", desc=True).execute().data

    def create_slide(self, title: str, body: str) -> Row:
        now = _now()
        return self._first(self._table("slides").insert(
            {"title": title, "body": body, "created_at": now, "updated_at": now}
        ).execute())

    def update_slide(self, slide_id: int, title: str, body: str) -> Row:
        return self._first(self._table("slides").update(
            {"title": title, "body": body, "updated_at": _now()}
        ).eq("id", slide_id).execute())

    def delete_slide(self, slide_id: int) -> None:
        self._first(self._table("slides").delete().eq("id", slide_id).execute())

    # Bible history
    def list_history(self, limit: int = 50) -> list[Row]:
        return (self._table("bible_history").select("*")
                .order("created_at", desc=True).order("id", desc=True).limit(limit).execute().data)

    def add_history(self, translation: str, reference: str) -> Row:
        (self._table("bible_history").delete()
         .eq("translation", translation).eq("reference", reference).execute())
        return self._first(self._table("bible_history").insert(
            {"translation": translation, "reference": reference, "created_at": _now()}
        ).execute())

    def clear_history(self) -> None:
        self._table("bible_history").delete().gte("id", 0).execute()

    # Media
    def list_media(self) -> list[Row]:
        return self._table("media").select("*").order("created_at", desc=True).execute().data

    def get_media(self, media_id: int) -> Row:
        return self._first(self._table("media").select("*").eq("id", media_id).execute())

    def add_media(self, name: str, kind: str, path: str, url: str) -> Row:
        return self._first(self._table("media").insert(
            {"name": name, "kind": kind, "path": path, "url": url, "created_at": _now()}
        ).execute())

    def delete_media(self, media_id: int) -> Row:
        row = self.get_media(media_id)
        self._table("media").delete().eq("id", media_id).execute()
        return row

    # Storage bucket helpers (used by the media router)
    def signed_upload(self, path: str) -> dict:
        res = self.client.storage.from_(self.bucket).create_signed_upload_url(path)
        return {"signed_url": res["signed_url"], "token": res["token"], "path": path}

    def public_url(self, path: str) -> str:
        return self.client.storage.from_(self.bucket).get_public_url(path)

    def remove_object(self, path: str) -> None:
        self.client.storage.from_(self.bucket).remove([path])
