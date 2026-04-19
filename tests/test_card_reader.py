"""Tests for card reader service."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.card_reader import (
    get_card_by_name,
    get_cards_by_race_and_cost,
    check_banlist,
    get_races,
)
from app.shared_models import Edition, Race, Type, Rarity, Card, Banlist


@pytest.mark.asyncio
async def test_get_card_by_name(test_session: AsyncSession, sample_card):
    """Test getting a card by name."""
    card = await get_card_by_name(test_session, sample_card.name)

    assert card is not None
    assert card["name"] == sample_card.name
    assert card["id"] == sample_card.id
    assert card["cost"] == sample_card.cost
    assert card["race_slug"] == "humanos"
    assert card["edition_slug"] == "core"


@pytest.mark.asyncio
async def test_get_card_by_name_not_found(test_session: AsyncSession):
    """Test getting a non-existent card."""
    card = await get_card_by_name(test_session, "Nonexistent Card")
    assert card is None


@pytest.mark.asyncio
async def test_get_cards_by_race_and_cost(test_session: AsyncSession, sample_card):
    """Test getting cards by race and cost."""
    cards = await get_cards_by_race_and_cost(
        test_session,
        race_slug="humanos",
        max_cost=5,
    )

    assert len(cards) >= 1
    # Our sample card should be in the results
    sample_in_results = any(c["name"] == sample_card.name for c in cards)
    assert sample_in_results


@pytest.mark.asyncio
async def test_get_cards_by_race_exclude_card(test_session: AsyncSession, sample_card):
    """Test excluding a specific card from results."""
    cards = await get_cards_by_race_and_cost(
        test_session,
        race_slug="humanos",
        max_cost=5,
        exclude_card_name=sample_card.name,
    )

    # Sample card should not be in results
    sample_in_results = any(c["name"] == sample_card.name for c in cards)
    assert not sample_in_results


@pytest.mark.asyncio
async def test_check_banlist(test_session: AsyncSession, sample_card):
    """Test checking banlist."""
    # Add a banlist entry
    ban_entry = Banlist(
        card_name=sample_card.name,
        format="racial_edicion",
        restriction="prohibida"
    )
    test_session.add(ban_entry)
    await test_session.commit()

    # Check banlist
    ban_status = await check_banlist(test_session, sample_card.name, "racial_edicion")

    assert ban_status is not None
    assert ban_status["card_name"] == sample_card.name
    assert ban_status["format"] == "racial_edicion"
    assert ban_status["restriction"] == "prohibida"


@pytest.mark.asyncio
async def test_check_banlist_not_banned(test_session: AsyncSession, sample_card):
    """Test checking banlist for non-banned card."""
    ban_status = await check_banlist(test_session, sample_card.name, "racial_edicion")
    assert ban_status is None


@pytest.mark.asyncio
async def test_get_races(test_session: AsyncSession, sample_card):
    """Test getting all races."""
    races = await get_races(test_session)

    assert len(races) >= 1
    # Test race should be in results
    test_race_in_results = any(r["slug"] == "humanos" for r in races)
    assert test_race_in_results
