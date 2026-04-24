"""Meta decks service — scrape, save, and query meta decks."""
import logging
import math
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import MetaDeck, MetaDeckCard
from app.services.scrapers.tor_myl import scrape_meta_decks

logger = logging.getLogger(__name__)

PAGE_SIZE = 20


async def scrape_and_save(
    session: AsyncSession,
    pages: int = 5,
    start_page: int = 1,
) -> dict:
    """Scrape tor.myl.cl and persist new decks to DB. Skips existing tor_ids."""
    logger.info("scrape_and_save | pages=%d start=%d", pages, start_page)

    raw_decks = await scrape_meta_decks(pages=pages, start_page=start_page)

    decks_found = len(raw_decks)
    decks_saved = 0
    errors = 0

    for raw in raw_decks:
        tor_id = raw.get("tor_id")
        if not tor_id:
            errors += 1
            continue

        # Skip if already exists
        existing = await session.scalar(
            select(MetaDeck).where(MetaDeck.tor_id == tor_id)
        )
        if existing:
            logger.debug("Skipping existing deck %s", tor_id)
            continue

        try:
            deck = MetaDeck(
                tor_id=tor_id,
                name=raw.get("name") or f"Mazo {tor_id}",
                author=raw.get("author"),
                race=raw.get("race"),
                race_slug=raw.get("race_slug"),
                format=raw.get("format"),
                tournament_name=raw.get("tournament_name"),
                tournament_position=raw.get("tournament_position"),
                card_count=raw.get("card_count", 0),
                scraped_at=datetime.utcnow(),
            )
            session.add(deck)
            await session.flush()  # get deck.id

            for card_data in raw.get("cards", []):
                card_name = card_data.get("card_name", "").strip()
                if not card_name:
                    continue
                card_entry = MetaDeckCard(
                    meta_deck_id=deck.id,
                    card_name=card_name,
                    quantity=card_data.get("quantity", 1),
                )
                session.add(card_entry)

            decks_saved += 1
        except Exception as e:
            logger.error("Error saving deck %s: %s", tor_id, e)
            errors += 1
            await session.rollback()
            continue

    await session.commit()

    return {
        "decks_found": decks_found,
        "decks_saved": decks_saved,
        "errors": errors,
        "message": f"Scraped {decks_found} decks, saved {decks_saved} new, {errors} errors",
    }


async def get_meta_decks(
    session: AsyncSession,
    page: int = 1,
    race_slug: Optional[str] = None,
    format_type: Optional[str] = None,
    search: Optional[str] = None,
) -> dict:
    """Return paginated list of meta decks with optional filters."""
    query = select(MetaDeck)

    if race_slug:
        query = query.where(MetaDeck.race_slug == race_slug)
    if format_type:
        query = query.where(MetaDeck.format == format_type)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                MetaDeck.name.ilike(pattern),
                MetaDeck.author.ilike(pattern),
                MetaDeck.tournament_name.ilike(pattern),
            )
        )

    # Total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_query) or 0

    pages = max(1, math.ceil(total / PAGE_SIZE))
    offset = (page - 1) * PAGE_SIZE

    query = query.order_by(MetaDeck.scraped_at.desc()).offset(offset).limit(PAGE_SIZE)
    result = await session.execute(query)
    decks = result.scalars().all()

    return {
        "decks": decks,
        "total": total,
        "page": page,
        "pages": pages,
    }


async def get_meta_deck_by_id(
    session: AsyncSession,
    tor_id: str,
) -> Optional[MetaDeck]:
    """Return a single meta deck by its tor_id."""
    result = await session.execute(
        select(MetaDeck).where(MetaDeck.tor_id == tor_id)
    )
    return result.scalar_one_or_none()
