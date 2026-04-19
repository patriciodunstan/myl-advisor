"""Tests for alternative finder service."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.alternative_finder import (
    find_alternatives,
    extract_keywords,
    calculate_similarity,
)
from app.llm.client import analyze_alternatives_with_llm
from app.shared_models import Edition, Race, Type, Rarity, Card


@pytest.mark.asyncio
async def test_find_alternatives(test_session: AsyncSession, sample_card):
    """Test finding alternatives for a card."""
    # Create similar cards
    race = await test_session.get(Race, 1)  # Test race
    edition = await test_session.get(Edition, 1)
    card_type = await test_session.get(Type, 1)
    rarity = await test_session.get(Rarity, 1)

    similar_card = Card(
        edid="TEST002",
        slug="similar-card",
        name="Similar Card",
        edition_id=edition.id,
        race_id=race.id,
        type_id=card_type.id,
        rarity_id=rarity.id,
        cost=2,  # Cheaper
        damage=2,
        ability="Furia. Destruir un aliado enemigo.",  # Shares keywords
        keywords="Furia, Destruir",
    )
    test_session.add(similar_card)

    # Create a card with no shared keywords
    different_card = Card(
        edid="TEST003",
        slug="different-card",
        name="Different Card",
        edition_id=edition.id,
        race_id=race.id,
        type_id=card_type.id,
        rarity_id=rarity.id,
        cost=4,
        damage=3,
        ability="Robar una carta del mazo del oponente.",  # Different keywords
        keywords="Robar",
    )
    test_session.add(different_card)

    await test_session.commit()

    # Find alternatives
    result = await find_alternatives(
        test_session,
        card_name=sample_card.name,
        format_type="racial_edicion",
    )

    assert result["meta"]["target_card_found"] is True
    assert result["meta"]["target_card"]["name"] == sample_card.name
    assert len(result["alternatives"]) >= 1

    # Similar card should be in alternatives with high similarity
    similar_in_results = any(
        alt["card"]["name"] == "Similar Card" for alt in result["alternatives"]
    )
    assert similar_in_results


@pytest.mark.asyncio
async def test_find_alternatives_card_not_found(test_session: AsyncSession):
    """Test finding alternatives for non-existent card."""
    result = await find_alternatives(
        test_session,
        card_name="Nonexistent Card",
        format_type="racial_edicion",
    )

    assert result["meta"]["target_card_found"] is False
    assert "error" in result["meta"]
    assert len(result["alternatives"]) == 0


@pytest.mark.asyncio
async def test_find_alternatives_with_max_cost(test_session: AsyncSession, sample_card):
    """Test finding alternatives with max cost constraint."""
    # Create a more expensive alternative
    race = await test_session.get(Race, 1)
    edition = await test_session.get(Edition, 1)
    card_type = await test_session.get(Type, 1)
    rarity = await test_session.get(Rarity, 1)

    expensive_card = Card(
        edid="TEST004",
        slug="expensive-card",
        name="Expensive Card",
        edition_id=edition.id,
        race_id=race.id,
        type_id=card_type.id,
        rarity_id=rarity.id,
        cost=10,  # Much more expensive
        damage=5,
        ability="Furia. Destruir todos los aliados enemigos.",
        keywords="Furia, Destruir",
    )
    test_session.add(expensive_card)
    await test_session.commit()

    # Find alternatives with max_cost=5
    result = await find_alternatives(
        test_session,
        card_name=sample_card.name,
        format_type="racial_edicion",
        max_cost=5,
    )

    # Expensive card should not be in results
    expensive_in_results = any(
        alt["card"]["name"] == "Expensive Card" for alt in result["alternatives"]
    )
    assert not expensive_in_results


@pytest.mark.asyncio
async def test_find_alternatives_filtered_by_banlist(test_session: AsyncSession, sample_card):
    """Test that banned cards are filtered out."""
    from app.shared_models import Banlist

    # Create a similar card and ban it
    race = await test_session.get(Race, 1)
    edition = await test_session.get(Edition, 1)
    card_type = await test_session.get(Type, 1)
    rarity = await test_session.get(Rarity, 1)

    banned_card = Card(
        edid="TEST005",
        slug="banned-card",
        name="Banned Card",
        edition_id=edition.id,
        race_id=race.id,
        type_id=card_type.id,
        rarity_id=rarity.id,
        cost=2,
        damage=2,
        ability="Furia. Destruir un aliado enemigo.",
        keywords="Furia, Destruir",
    )
    test_session.add(banned_card)

    ban_entry = Banlist(
        card_name="Banned Card",
        format="racial_edicion",
        restriction="prohibida"
    )
    test_session.add(ban_entry)
    await test_session.commit()

    # Find alternatives
    result = await find_alternatives(
        test_session,
        card_name=sample_card.name,
        format_type="racial_edicion",
    )

    # Banned card should not be in results
    banned_in_results = any(
        alt["card"]["name"] == "Banned Card" for alt in result["alternatives"]
    )
    assert not banned_in_results


def test_extract_keywords():
    """Test keyword extraction."""
    ability = "Furia. Cuando esta carta entra en juego, destruye un objetivo. Indestructible mientras atacas."
    keywords = extract_keywords(ability)

    assert "Furia" in keywords
    assert "Destruir" in keywords
    assert "Indestructible" in keywords
    assert len(keywords) >= 3


def test_extract_keywords_none():
    """Test keyword extraction with None."""
    keywords = extract_keywords(None)
    assert len(keywords) == 0


def test_extract_keywords_empty():
    """Test keyword extraction with empty string."""
    keywords = extract_keywords("")
    assert len(keywords) == 0


def test_calculate_similarity():
    """Test similarity calculation."""
    target = {"Furia", "Destruir", "Indestructible"}
    candidate = {"Furia", "Destruir", "Robar"}

    similarity = calculate_similarity(target, candidate)

    # Shared: Furia, Destruir (2)
    # Total unique: Furia, Destruir, Indestructible, Robar (4)
    # Similarity = 2/4 * 100 = 50
    assert similarity == 50


def test_calculate_similarity_no_match():
    """Test similarity calculation with no shared keywords."""
    target = {"Furia", "Destruir"}
    candidate = {"Robar", "Generar"}

    similarity = calculate_similarity(target, candidate)

    assert similarity == 0


def test_calculate_similarity_perfect_match():
    """Test similarity calculation with perfect match."""
    target = {"Furia", "Destruir"}
    candidate = {"Furia", "Destruir"}

    similarity = calculate_similarity(target, candidate)

    assert similarity == 100


@pytest.mark.asyncio
async def test_alternatives_with_llm_analysis(test_session: AsyncSession, sample_card):
    """Test that LLM analysis is included when API key is configured."""
    # Create similar card
    from app.shared_models import Edition
    race = await test_session.get(Race, 1)
    edition = await test_session.get(Edition, 1)
    card_type = await test_session.get(Type, 1)
    rarity = await test_session.get(Rarity, 1)

    similar = Card(
        edid="TEST010",
        slug="similar-llm",
        name="Similar LLM Card",
        edition_id=edition.id,
        race_id=race.id,
        type_id=card_type.id,
        rarity_id=rarity.id,
        cost=4,
        damage=2,
        ability="Furia. Destruir un aliado objetivo.",
        keywords="Furia, Destruir",
    )
    test_session.add(similar)
    await test_session.commit()

    # Test with invalid API key (test_key) - should return None for llm_analysis
    result = await find_alternatives(
        test_session,
        card_name=sample_card.name,
        format_type="racial_edicion",
    )

    llm_result = await analyze_alternatives_with_llm(
        session=test_session,
        target_card=result["meta"]["target_card"],
        alternatives=result["alternatives"],
        request_data={
            "card_name": sample_card.name,
            "format": "racial_edicion",
            "max_rarity": None,
            "max_cost": None,
        },
    )

    # With test_key, LLM analysis should be None (keyword-only mode)
    assert llm_result is None
    assert result["meta"]["target_card_found"] is True
