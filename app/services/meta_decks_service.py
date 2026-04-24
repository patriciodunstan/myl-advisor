"""Meta decks service — scrape, save, and query meta decks."""
import logging
import math
from collections import Counter
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import MetaDeck, MetaDeckCard
from app.shared_models import Card, Race
from app.services.scrapers.tor_myl import scrape_meta_decks

logger = logging.getLogger(__name__)

PAGE_SIZE = 20


async def _resolve_card_ids(
    session: AsyncSession,
    card_ids: list[int],
) -> dict[int, dict]:
    """
    Resolve a list of card IDs to card data from our DB.
    Returns {card_id: {name, race_id, race_slug, race_name}}.
    """
    if not card_ids:
        return {}

    result = await session.execute(
        select(Card, Race)
        .outerjoin(Race, Card.race_id == Race.id)
        .where(Card.id.in_(card_ids))
    )
    rows = result.all()

    resolved = {}
    for card, race in rows:
        resolved[card.id] = {
            "name": card.name,
            "race_id": card.race_id,
            "race_slug": race.slug if race else None,
            "race_name": race.name if race else None,
        }
    return resolved


def _infer_race(card_data: dict[int, dict], card_counts: dict[int, int]) -> tuple[Optional[str], Optional[str]]:
    """
    Infer the deck's primary race from its cards.
    Returns (race_slug, race_name).
    """
    race_counter: Counter = Counter()
    for card_id, quantity in card_counts.items():
        info = card_data.get(card_id)
        if info and info.get("race_slug"):
            race_counter[info["race_slug"]] += quantity

    if not race_counter:
        return None, None

    top_race_slug = race_counter.most_common(1)[0][0]
    # Find race name from any card with that slug
    for info in card_data.values():
        if info.get("race_slug") == top_race_slug:
            return top_race_slug, info.get("race_name")

    return top_race_slug, None


async def scrape_and_save(
    session: AsyncSession,
    pages: int = 5,
    start_page: int = 1,
) -> dict:
    """Scrape api.myl.cl and persist new decks. Skips existing slugs."""
    logger.info("scrape_and_save | pages=%d start=%d", pages, start_page)

    raw_decks = await scrape_meta_decks(pages=pages, start_page=start_page)

    decks_found = len(raw_decks)
    decks_saved = 0
    errors = 0

    for raw in raw_decks:
        slug = raw.get("slug")
        if not slug:
            errors += 1
            continue

        # Skip if already exists
        existing = await session.scalar(
            select(MetaDeck).where(MetaDeck.tor_id == slug)
        )
        if existing:
            logger.debug("Skipping existing deck %s", slug)
            continue

        try:
            card_counts: dict[int, int] = raw.get("card_counts", {})
            card_ids = list(card_counts.keys())

            # Resolve card IDs → names and race info from our DB
            card_data = await _resolve_card_ids(session, card_ids)

            # Infer race from cards
            race_slug, race_name = _infer_race(card_data, card_counts)

            deck = MetaDeck(
                tor_id=slug,
                name=raw.get("title") or slug,
                author=raw.get("author"),
                race=race_name,
                race_slug=race_slug,
                format=None,  # API doesn't expose format
                tournament_name=None,
                tournament_position=None,
                card_count=sum(card_counts.values()),
                scraped_at=datetime.utcnow(),
            )
            session.add(deck)
            await session.flush()

            # Save card entries using resolved names
            for card_id, quantity in card_counts.items():
                card_info = card_data.get(card_id)
                card_name = card_info["name"] if card_info else f"[Card #{card_id}]"
                session.add(MetaDeckCard(
                    meta_deck_id=deck.id,
                    card_name=card_name,
                    quantity=quantity,
                ))

            decks_saved += 1
        except Exception as e:
            logger.error("Error saving deck %s: %s", slug, e)
            errors += 1
            await session.rollback()
            continue

    await session.commit()
    logger.info("scrape_and_save done | found=%d saved=%d errors=%d", decks_found, decks_saved, errors)

    return {
        "decks_found": decks_found,
        "decks_saved": decks_saved,
        "errors": errors,
        "message": f"Scrapeados {decks_found} mazos, guardados {decks_saved} nuevos, {errors} errores",
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

    filters = []
    if race_slug:
        filters.append(MetaDeck.race_slug == race_slug)
    if format_type:
        filters.append(MetaDeck.format == format_type)
    if search:
        pattern = f"%{search}%"
        filters.append(or_(
            MetaDeck.name.ilike(pattern),
            MetaDeck.author.ilike(pattern),
        ))
    if filters:
        query = query.where(and_(*filters))

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
    """Return a single meta deck by its tor_id (slug)."""
    result = await session.execute(
        select(MetaDeck).where(MetaDeck.tor_id == tor_id)
    )
    return result.scalar_one_or_none()
