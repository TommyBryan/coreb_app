import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import songs
from .config import get_settings
from .routers import bible, media, slides
from .routers import songs as songs_router
from .storage import get_store

log = logging.getLogger("coreb")

PAGES = {
    "": "index.html",
    "bible": "bible.html",
    "songs": "songs.html",
    "slides": "slides.html",
    "media": "media.html",
    "output": "output.html",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    try:
        added = songs.seed_if_empty(get_store(), settings.data_dir / "songs.csv")
        if added:
            log.info("Seeded %d songs from data/songs.csv", added)
    except Exception:  # a database hiccup must not keep the app from starting
        log.exception("Song seeding failed")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="COREB", lifespan=lifespan)

    app.include_router(bible.router)
    app.include_router(songs_router.router)
    app.include_router(slides.router)
    app.include_router(media.router)

    @app.get("/api/config")
    def config():
        return {"storage": "supabase" if settings.use_supabase else "local"}

    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
    if not settings.use_supabase:
        settings.media_dir.mkdir(parents=True, exist_ok=True)
        app.mount("/media-files", StaticFiles(directory=settings.media_dir), name="media-files")

    @app.get("/{page}", include_in_schema=False)
    @app.get("/", include_in_schema=False)
    def page(page: str = ""):
        name = PAGES.get(page.removesuffix(".html").replace("index", ""))
        if not name:
            raise HTTPException(404, "Page not found")
        return FileResponse(settings.static_dir / name)

    return app


app = create_app()
