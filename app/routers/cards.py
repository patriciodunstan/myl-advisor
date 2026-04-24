"""Cards search, races, and image proxy endpoints."""
import logging
import httpx
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.card_reader import search_cards_by_name, get_races
from app.shared_models import Card

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/advisor", tags=["cards"])

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=15.0, follow_redirects=True)
    return _http_client


@router.get("/cards/search")
async def search_cards(
    q: str = Query(..., min_length=1, description="Partial card name to search"),
    limit: int = Query(10, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """Search cards by name (case-insensitive, deduplicated). Used for autocomplete."""
    logger.info("GET /advisor/cards/search | q=%r limit=%d", q, limit)
    results = await search_cards_by_name(db, q, limit)
    return {"results": results}


@router.get("/races")
async def list_races(db: AsyncSession = Depends(get_db)):
    """List all races. Used to populate race dropdowns in the frontend."""
    logger.info("GET /advisor/races")
    races = await get_races(db)
    return {"races": races}


@router.get("/images/{path:path}")
async def proxy_card_image(path: str):
    """Proxy card images from api.myl.cl through our backend to avoid CORS issues."""
    remote_url = f"https://api.myl.cl/static/cards/{path}"
    try:
        client = _get_http_client()
        resp = await client.get(remote_url)
        if resp.status_code == 200:
            content_type = resp.headers.get("content-type", "image/png")
            return Response(content=resp.content, media_type=content_type)
        logger.warning("Image proxy: upstream %d for %s", resp.status_code, path)
        raise HTTPException(status_code=404, detail="Image not found")
    except httpx.RequestError as exc:
        logger.error("Image proxy error for %s: %s", path, exc)
        raise HTTPException(status_code=502, detail="Image fetch failed")


class CardsByNamesRequest(BaseModel):
    names: list[str]


@router.post("/cards/by-names")
async def get_cards_by_names(
    body: CardsByNamesRequest,
    db: AsyncSession = Depends(get_db),
):
    """Return card info (including image_path) for a list of card names."""
    if not body.names:
        return {"cards": {}}

    result = await db.execute(
        select(Card).where(Card.name.in_(body.names))
    )
    cards = result.scalars().all()

    cards_map: dict[str, dict] = {}
    for card in cards:
        image_path = card.image_path or (
            f"{card.edition_id}/{card.edid}.png" if card.edid else None
        )
        cards_map[card.name] = {"image_path": image_path}

    return {"cards": cards_map}
