"""Prices endpoint - Scrapes prices from Chilean MyL card stores."""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.database import get_db
from app.schemas import PriceInfo, PriceResponse
from app.services.scrapers.aggregator import (
    search_all_stores,
    save_prices_to_db,
    get_cached_prices,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/advisor", tags=["advisor"])


def _scrape_result_to_price_info(result) -> PriceInfo:
    """Convert ScrapeResult to PriceInfo schema."""
    return PriceInfo(
        source=result.store_name,
        price_clp=result.price_clp,
        price_usd=None,  # USD prices not scraped yet
        availability=result.availability,
        url=result.url,
        updated_at=result.scraped_at,
    )


def _calculate_stats(price_infos: List[PriceInfo]) -> tuple[Optional[int], Optional[int]]:
    """Calculate average and minimum price from PriceInfo list."""
    valid_prices = [p.price_clp for p in price_infos if p.price_clp is not None]

    if not valid_prices:
        return None, None

    avg_price = sum(valid_prices) // len(valid_prices)
    min_price = min(valid_prices)

    return avg_price, min_price


@router.get("/prices/{card_name}", response_model=PriceResponse, tags=["advisor"])
async def get_prices(
    card_name: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get prices for a card from Chilean MyL card stores.

    This endpoint scrapes prices in real-time from:
    - cartasmitos.cl (WooCommerce)
    - huntercardtcg.com (WooCommerce)
    - lacuevatcg.cl (Shopify)

    Prices are cached for 24 hours to reduce server load.

    Parameters:
    - card_name: Name of the card to look up

    Returns:
    - prices: List of prices from different stores
    - avg_price_clp: Average price in Chilean Pesos
    - min_price_clp: Minimum price found
    """
    logger.info("GET /prices/%s", card_name)

    # Try to get cached prices first (last 24 hours)
    cached_results = await get_cached_prices(db, card_name, max_age_hours=24)

    if cached_results:
        # Use cached results
        price_infos = [_scrape_result_to_price_info(r) for r in cached_results]
        avg_price, min_price = _calculate_stats(price_infos)

        response = PriceResponse(
            card_name=card_name,
            prices=price_infos,
            avg_price_clp=avg_price,
            min_price_clp=min_price,
        )

        logger.info("GET /prices/%s → cached response with %d sources (avg: %s CLP, min: %s CLP)",
                    card_name, len(price_infos), avg_price, min_price)

        return response

    # No cache or cache expired - scrape all stores
    scrape_results = await search_all_stores(card_name)

    if not scrape_results:
        # No results found
        logger.warning("GET /prices/%s → no results found from any store", card_name)
        return PriceResponse(
            card_name=card_name,
            prices=[],
            avg_price_clp=None,
            min_price_clp=None,
        )

    # Save new prices to database
    await save_prices_to_db(db, scrape_results)

    # Build response
    price_infos = [_scrape_result_to_price_info(r) for r in scrape_results]
    avg_price, min_price = _calculate_stats(price_infos)

    response = PriceResponse(
        card_name=card_name,
        prices=price_infos,
        avg_price_clp=avg_price,
        min_price_clp=min_price,
    )

    logger.info("GET /prices/%s → fresh scrape with %d sources (avg: %s CLP, min: %s CLP)",
                card_name, len(price_infos), avg_price, min_price)

    return response
