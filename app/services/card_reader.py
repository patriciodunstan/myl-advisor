"""Card Reader Service - Query shared MyL database for cards."""
import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.shared_models import Card, Edition, Race, Type, Rarity, Banlist


logger = logging.getLogger(__name__)


async def get_card_by_name(
    session: AsyncSession,
    card_name: str,
) -> Optional[dict]:
    """Get a single card by name with joins."""
    logger.info("get_card_by_name | card_name=%r", card_name)

    query = (
        select(Card)
        .options(
            selectinload(Card.edition),
            selectinload(Card.race),
            selectinload(Card.type),
            selectinload(Card.rarity),
        )
        .where(Card.name == card_name)
        .limit(1)
    )
    result = await session.execute(query)
    card = result.scalar_one_or_none()

    if card:
        return _card_to_dict(card)
    else:
        logger.warning("get_card_by_name | card_name=%r not found", card_name)
        return None


async def get_cards_by_race_and_cost(
    session: AsyncSession,
    race_slug: str,
    max_cost: Optional[int] = None,
    exclude_card_name: Optional[str] = None,
    limit: int = 50,
) -> List[dict]:
    """Get cards of a specific race, optionally filtered by cost."""
    logger.info(
        "get_cards_by_race_and_cost | race=%r max_cost=%s exclude=%s limit=%d",
        race_slug, max_cost, exclude_card_name, limit
    )

    query = (
        select(Card)
        .join(Race, Card.race_id == Race.id)
        .options(
            selectinload(Card.edition),
            selectinload(Card.race),
            selectinload(Card.type),
            selectinload(Card.rarity),
        )
        .where(Race.slug == race_slug)
    )

    if max_cost is not None:
        query = query.where(Card.cost <= max_cost)

    if exclude_card_name:
        query = query.where(Card.name != exclude_card_name)

    query = query.order_by(Card.cost.asc(), Card.name.asc()).limit(limit)

    result = await session.execute(query)
    cards = result.scalars().all()

    cards_data = [_card_to_dict(card) for card in cards]
    logger.info("get_cards_by_race_and_cost → %d cards", len(cards_data))
    return cards_data


async def check_banlist(
    session: AsyncSession,
    card_name: str,
    format_type: str = "racial_edicion",
) -> Optional[dict]:
    """Check if a card is on the banlist for a format."""
    logger.info("check_banlist | card_name=%r format=%r", card_name, format_type)

    query = select(Banlist).where(
        Banlist.card_name == card_name,
        Banlist.format == format_type
    )
    result = await session.execute(query)
    ban_entry = result.scalar_one_or_none()

    if ban_entry:
        result_dict = {
            "card_name": ban_entry.card_name,
            "edition": ban_entry.edition,
            "format": ban_entry.format,
            "restriction": ban_entry.restriction,
        }
        logger.info("check_banlist | %r → restriction=%s", card_name, result_dict.get("restriction"))
        return result_dict
    else:
        logger.debug("check_banlist | %r → no restriction found", card_name)
        return None


async def get_races(session: AsyncSession) -> List[dict]:
    """Get all races."""
    logger.info("get_races")

    query = select(Race).order_by(Race.name)
    result = await session.execute(query)
    races = [{"id": r.id, "slug": r.slug, "name": r.name} for r in result.scalars().all()]

    logger.info("get_races → %d races", len(races))
    return races


def _card_to_dict(card: Card) -> dict:
    """Convert Card model to dict with joined data."""
    return {
        "id": card.id,
        "edid": card.edid,
        "slug": card.slug,
        "name": card.name,
        "cost": card.cost,
        "damage": card.damage,
        "ability": card.ability,
        "keywords": card.keywords,
        "image_path": card.image_path,
        "edition_id": card.edition_id,
        "edition_title": card.edition.title if card.edition else None,
        "edition_slug": card.edition.slug if card.edition else None,
        "race_id": card.race_id,
        "race_name": card.race.name if card.race else None,
        "race_slug": card.race.slug if card.race else None,
        "type_id": card.type_id,
        "type_name": card.type.name if card.type else None,
        "type_slug": card.type.slug if card.type else None,
        "rarity_id": card.rarity_id,
        "rarity_name": card.rarity.name if card.rarity else None,
        "rarity_slug": card.rarity.slug if card.rarity else None,
    }
