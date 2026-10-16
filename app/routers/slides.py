from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..storage import NotFound, Store, get_store

router = APIRouter(prefix="/api/slides", tags=["slides"])


class SlideIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field("", max_length=20_000)


@router.get("")
def list_slides(store: Store = Depends(get_store)):
    return store.list_slides()


@router.post("", status_code=201)
def create_slide(slide: SlideIn, store: Store = Depends(get_store)):
    return store.create_slide(slide.title.strip(), slide.body)


@router.put("/{slide_id}")
def update_slide(slide_id: int, slide: SlideIn, store: Store = Depends(get_store)):
    try:
        return store.update_slide(slide_id, slide.title.strip(), slide.body)
    except NotFound:
        raise HTTPException(404, "Slide not found")


@router.delete("/{slide_id}")
def delete_slide(slide_id: int, store: Store = Depends(get_store)):
    try:
        store.delete_slide(slide_id)
    except NotFound:
        raise HTTPException(404, "Slide not found")
    return {"ok": True}
