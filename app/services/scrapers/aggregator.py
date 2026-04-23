"""Price aggregator that searches all stores in parallel."""
import logging
import asyncio
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from .base import BaseScraper, ScrapeResult
from .cartasmitos import CartasMitosScraper
from .huntercard import HunterCardScraper
from .lacuevatcg import LaCuevaScraper
from .mesaredonda import MesaRedondaScraper

logger = logging.getLogger(__name__)


# All available scrapers
SCRAPERS: List[BaseScraper] = []


def get_scrapers() -> List[BaseScraper]:
    """Get initialized scraper instances (lazy init)."""
    global SCRAPERS
    if not SCRAPERS:
        SCRAPERS = [
            CartasMitosScraper(),
            HunterCardScraper(),
            LaCuevaScraper(),
            MesaRedondaScraper(),
        ]
    return SCRAPERS


async def search_all_stores(card_name: str) -> List[ScrapeResult]:
    """Search all stores for a card in parallel."""
    scrapers = get_scrapers()

    tasks = [scraper.search_card(card_name) for scraper in scrapers]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error("Scraper %s failed: %s", scrapers[i].store_name, result)
        elif isinstance(result, list):
            all_results.extend(result)

    logger.info("Found %d total results for '%s' across %d stores",
                len(all_results), card_name, len(scrapers))
    return all_results


async def save_prices_to_db(session: AsyncSession, results: List[ScrapeResult]):
    """Save scraped prices to database."""
    from app.database import CardPrice
    from app.services.card_reader import get_card_by_name

    for result in results:
        # Try to find card in DB
        card = await get_card_by_name(session, result.card_name)
        if not card:
            continue

        price_entry = CardPrice(
            card_id=card["id"],
            card_name=result.card_name,
            source=result.store_name,
            price_clp=result.price_clp,
            availability=result.availability,
            url=result.url,
        )
        session.add(price_entry)

    await session.flush()
    logger.info("Saved %d price entries to database", len(results))


async def get_cached_prices(session: AsyncSession, card_name: str, max_age_hours: int = 24) -> List[ScrapeResult]:
    """Get cached prices from database if they exist and are recent."""
    from app.database import CardPrice
    from datetime import datetime, timedelta

    cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

    query = (
        select(CardPrice)
        .where(
            and_(
                CardPrice.card_name == card_name,
                CardPrice.updated_at >= cutoff_time
            )
        )
        .order_by(CardPrice.updated_at.desc())
    )

    result = await session.execute(query)
    db_prices = result.scalars().all()

    if not db_prices:
        return []

    # Convert to ScrapeResult objects
    cached_results = []
    seen = set()  # Avoid duplicates by (store_name, title)
    for price in db_prices:
        key = (price.source, price.url or "")
        if key in seen:
            continue
        seen.add(key)

        cached_results.append(ScrapeResult(
            card_name=price.card_name,
            store_name=price.source,
            price_clp=price.price_clp,
            availability=price.availability or "unknown",
            url=price.url,
            title=price.card_name,  # DB doesn't store title, use card_name
            scraped_at=price.updated_at,
        ))

    logger.info("Found %d cached prices for '%s' (last %d hours)", len(cached_results), card_name, max_age_hours)
    return cached_results


async def close_all_scrapers():
    """Close all scraper HTTP clients."""
    for scraper in get_scrapers():
        await scraper.close()
