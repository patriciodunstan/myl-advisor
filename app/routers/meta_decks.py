"""Router for meta decks endpoints."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import (
    MetaDeckDetailResponse,
    MetaDeckListResponse,
    ScrapeMetaDecksRequest,
    ScrapeMetaDecksResponse,
)
from app.services.meta_decks_service import (
    get_meta_deck_by_id,
    get_meta_decks,
    scrape_and_save,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/advisor", tags=["meta-decks"])


@router.get(
    "/meta-decks",
    response_model=MetaDeckListResponse,
    summary="List meta decks",
    description="Return paginated list of meta decks scraped from tor.myl.cl",
)
async def list_meta_decks(
    page: int = Query(default=1, ge=1),
    race_slug: Optional[str] = Query(default=None),
    format: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None, min_length=2),
    db: AsyncSession = Depends(get_db),
) -> MetaDeckListResponse:
    logger.info("list_meta_decks | page=%d race=%s format=%s search=%s", page, race_slug, format, search)
    result = await get_meta_decks(
        session=db,
        page=page,
        race_slug=race_slug,
        format_type=format,
        search=search,
    )
    return MetaDeckListResponse(**result)


@router.get(
    "/meta-decks/{tor_id}",
    response_model=MetaDeckDetailResponse,
    summary="Get meta deck detail",
    description="Return full deck with card list by tor_id",
)
async def get_meta_deck(
    tor_id: str,
    db: AsyncSession = Depends(get_db),
) -> MetaDeckDetailResponse:
    logger.info("get_meta_deck | tor_id=%s", tor_id)
    deck = await get_meta_deck_by_id(db, tor_id)
    if not deck:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deck '{tor_id}' not found",
        )
    return MetaDeckDetailResponse(deck=deck)


@router.post(
    "/meta-decks/scrape",
    response_model=ScrapeMetaDecksResponse,
    summary="Scrape meta decks",
    description="Manually trigger scraping of tor.myl.cl and persist new decks",
)
async def scrape_meta_decks_endpoint(
    request: ScrapeMetaDecksRequest,
    db: AsyncSession = Depends(get_db),
) -> ScrapeMetaDecksResponse:
    logger.info("scrape_meta_decks | pages=%d start=%d", request.pages, request.start_page)
    try:
        result = await scrape_and_save(
            session=db,
            pages=request.pages,
            start_page=request.start_page,
        )
        return ScrapeMetaDecksResponse(**result)
    except Exception as e:
        logger.error("scrape_meta_decks | error=%s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scraping failed: {str(e)}",
        )
