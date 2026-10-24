from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .routers import bible, media, slides, songs

PAGES = {
    "": "index.html",
    "bible": "bible.html",
    "songs": "songs.html",
    "slides": "slides.html",
    "media": "media.html",
    "output": "output.html",
}


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="COREB")

    app.include_router(bible.router)
    app.include_router(songs.router)
    app.include_router(slides.router)
    app.include_router(media.router)

    settings.media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
    app.mount("/media-files", StaticFiles(directory=settings.media_dir), name="media-files")

    @app.get("/", include_in_schema=False)
    @app.get("/{page}", include_in_schema=False)
    def page(page: str = ""):
        name = PAGES.get(page.removesuffix(".html").replace("index", ""))
        if not name:
            raise HTTPException(404, "Page not found")
        return FileResponse(settings.static_dir / name, headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
