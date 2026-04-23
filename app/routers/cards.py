"""Cards search and races endpoints — supports frontend autocomplete and dropdowns."""
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.card_reader import search_cards_by_name, get_races

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/advisor", tags=["cards"])


@router.get("/cards/search")
async def search_cards(
    q: str = Query(..., min_length=1, description="Partial card name to search"),
    limit: int = Query(10, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """Search cards by name (case-insensitive partial match). Used for autocomplete."""
    logger.info("GET /advisor/cards/search | q=%r limit=%d", q, limit)
    results = await search_cards_by_name(db, q, limit)
    return {"results": results}


@router.get("/races")
async def list_races(db: AsyncSession = Depends(get_db)):
    """List all races. Used to populate race dropdowns in the frontend."""
    logger.info("GET /advisor/races")
    races = await get_races(db)
    return {"races": races}
