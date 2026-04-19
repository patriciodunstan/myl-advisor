"""Tests for synergy analyzer service."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.synergy_analyzer import find_synergies, _get_synergy_category, _check_synergy
from app.shared_models import Edition, Race, Type, Rarity, Card


@pytest.mark.asyncio
async def test_find_synergies_with_removal_draw(test_session: AsyncSession):
    """Test finding synergies with removal and draw effects."""
    # Create related entities
    edition = Edition(id=10, slug="test", title="Test Edition")
    race = Race(id=10, slug="test_race", name="Test Race")
    type_obj = Type(id=10, slug="aliado", name="Aliado")
    rarity = Rarity(id=10, slug="comun", name="Común")

    test_session.add(edition)
    test_session.add(race)
    test_session.add(type_obj)
    test_session.add(rarity)
    await test_session.flush()

    # Create input card with removal
    removal_card = Card(
        edid="SYN001",
        slug="removal-card",
        name="Removal Card",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity.id,
        cost=3,
        damage=2,
        ability="Destruir un aliado enemigo.",
        keywords="Destruir",
    )
    test_session.add(removal_card)

    # Create candidate card with draw
    draw_card = Card(
        edid="SYN002",
        slug="draw-card",
        name="Draw Card",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity.id,
        cost=2,
        damage=1,
        ability="Robar una carta del mazo.",
        keywords="Robar",
    )
    test_session.add(draw_card)

    await test_session.commit()

    # Find synergies
    result = await find_synergies(
        test_session,
        card_names=["Removal Card"],
        race_slug="test_race",
        format_type="racial_edicion",
    )

    assert result["meta"]["synergies_found"] >= 1
    assert len(result["synergies"]) >= 1

    # Check that we found the removal+draw synergy
    synergies = result["synergies"]
    removal_draw_synergy = any(
        "Removal Card" in [c["name"] for c in s["cards"]] and
        "Draw Card" in [c["name"] for c in s["cards"]]
        for s in synergies
    )
    assert removal_draw_synergy


@pytest.mark.asyncio
async def test_find_synergies_card_not_found(test_session: AsyncSession):
    """Test finding synergies for non-existent card."""
    result = await find_synergies(
        test_session,
        card_names=["Nonexistent Card"],
        race_slug="test",
        format_type="racial_edicion",
    )

    assert result["meta"]["synergies_found"] == 0
    assert "error" in result["meta"]


@pytest.mark.asyncio
async def test_find_synergies_multiple_input_cards(test_session: AsyncSession):
    """Test finding synergies with multiple input cards."""
    # Create related entities
    edition = Edition(id=20, slug="test2", title="Test Edition 2")
    race = Race(id=20, slug="test_race2", name="Test Race 2")
    type_obj = Type(id=20, slug="aliado", name="Aliado")
    rarity = Rarity(id=20, slug="comun", name="Común")

    test_session.add(edition)
    test_session.add(race)
    test_session.add(type_obj)
    test_session.add(rarity)
    await test_session.flush()

    # Create input cards
    card1 = Card(
        edid="SYN010",
        slug="card1",
        name="Card 1",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity.id,
        cost=3,
        ability="Destruir un aliado enemigo.",
        keywords="Destruir",
    )
    test_session.add(card1)

    card2 = Card(
        edid="SYN011",
        slug="card2",
        name="Card 2",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity.id,
        cost=2,
        ability="Robar una carta.",
        keywords="Robar",
    )
    test_session.add(card2)

    # Create candidate card
    candidate = Card(
        edid="SYN012",
        slug="candidate",
        name="Candidate Card",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity.id,
        cost=4,
        ability="Vida +2 y Armadura +2.",
        keywords="Vida, Armadura",
    )
    test_session.add(candidate)

    await test_session.commit()

    # Find synergies
    result = await find_synergies(
        test_session,
        card_names=["Card 1", "Card 2"],
        race_slug="test_race2",
        format_type="racial_edicion",
    )

    assert len(result["meta"]["input_cards"]) == 2


@pytest.mark.asyncio
async def test_find_synergies_filtered_by_banlist(test_session: AsyncSession):
    """Test that banned cards are not included as synergies."""
    from app.shared_models import Banlist

    # Create related entities
    edition = Edition(id=30, slug="test3", title="Test Edition 3")
    race = Race(id=30, slug="test_race3", name="Test Race 3")
    type_obj = Type(id=30, slug="aliado", name="Aliado")
    rarity = Rarity(id=30, slug="comun", name="Común")

    test_session.add(edition)
    test_session.add(race)
    test_session.add(type_obj)
    test_session.add(rarity)
    await test_session.flush()

    # Create input card
    input_card = Card(
        edid="SYN020",
        slug="input",
        name="Input Card",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity.id,
        cost=3,
        ability="Destruir un aliado enemigo.",
        keywords="Destruir",
    )
    test_session.add(input_card)

    # Create banned candidate
    banned = Card(
        edid="SYN021",
        slug="banned-syn",
        name="Banned Syn",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity.id,
        cost=2,
        ability="Robar una carta.",
        keywords="Robar",
    )
    test_session.add(banned)

    ban_entry = Banlist(
        card_name="Banned Syn",
        format="racial_edicion",
        restriction="prohibida"
    )
    test_session.add(ban_entry)

    await test_session.commit()

    # Find synergies
    result = await find_synergies(
        test_session,
        card_names=["Input Card"],
        race_slug="test_race3",
        format_type="racial_edicion",
    )

    # Banned card should not be in synergies
    for synergy in result["synergies"]:
        card_names = [c["name"] for c in synergy["cards"]]
        assert "Banned Syn" not in card_names


def test_get_synergy_category():
    """Test synergy category detection."""
    # Test various keywords
    assert _get_synergy_category({"Destruir", "Anular"}) == "removal"
    assert _get_synergy_category({"Robar", "Mazo"}) == "draw"
    assert _get_synergy_category({"Vida", "Armadura"}) == "buff"
    assert _get_synergy_category({"Imbloqueable", "Vuelo"}) == "evasion"
    assert _get_synergy_category({"Exhumar", "Cementerio"}) == "summon"
    assert _get_synergy_category({"Indestructible", "Inmunidad"}) == "protection"
    assert _get_synergy_category({"Oro Inicial", "Generar"}) == "resource"
    assert _get_synergy_category(set()) == "other"


def test_check_synergy():
    """Test synergy detection between categories."""
    # Removal + Draw = combo
    has_synergy, synergy_type, explanation = _check_synergy("removal", "draw")
    assert has_synergy is True
    assert synergy_type == "combo"
    assert "remueve" in explanation.lower()

    # Buff + Evasion = combo
    has_synergy, synergy_type, explanation = _check_synergy("buff", "evasion")
    assert has_synergy is True
    assert synergy_type == "combo"

    # Summon + Protection = engine
    has_synergy, synergy_type, explanation = _check_synergy("summon", "protection")
    assert has_synergy is True
    assert synergy_type == "engine"

    # No synergy
    has_synergy, synergy_type, explanation = _check_synergy("other", "other")
    assert has_synergy is False
    assert synergy_type == ""
    assert explanation == ""


@pytest.mark.asyncio
async def test_find_synergies_scoring(test_session: AsyncSession):
    """Test that synergies are scored and sorted correctly."""
    # Create related entities
    edition = Edition(id=40, slug="test4", title="Test Edition 4")
    race = Race(id=40, slug="test_race4", name="Test Race 4")
    type_obj = Type(id=40, slug="aliado", name="Aliado")
    rarity = Rarity(id=40, slug="comun", name="Común")

    test_session.add(edition)
    test_session.add(race)
    test_session.add(type_obj)
    test_session.add(rarity)
    await test_session.flush()

    # Create input card
    input_card = Card(
        edid="SYN030",
        slug="input-score",
        name="Input Score",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity.id,
        cost=3,
        ability="Destruir un aliado enemigo.",
        keywords="Destruir",
    )
    test_session.add(input_card)

    # Create two candidates with shared keywords
    candidate1 = Card(
        edid="SYN031",
        slug="candidate1",
        name="High Synergy",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity.id,
        cost=2,
        ability="Destruir y Robar una carta.",
        keywords="Destruir, Robar",
    )
    test_session.add(candidate1)

    candidate2 = Card(
        edid="SYN032",
        slug="candidate2",
        name="Low Synergy",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity.id,
        cost=5,
        ability="Robar una carta.",
        keywords="Robar",
    )
    test_session.add(candidate2)

    await test_session.commit()

    # Find synergies
    result = await find_synergies(
        test_session,
        card_names=["Input Score"],
        race_slug="test_race4",
        format_type="racial_edicion",
        limit=10,
    )

    # Check that synergies are sorted by score (highest first)
    if len(result["synergies"]) >= 2:
        scores = [s["synergy_score"] for s in result["synergies"]]
        assert scores == sorted(scores, reverse=True)

    # Check that high synergy card has better score than low synergy
    high_synergy = next(
        (s for s in result["synergies"]
         if "High Synergy" in [c["name"] for c in s["cards"]]),
        None
    )
    low_synergy = next(
        (s for s in result["synergies"]
         if "Low Synergy" in [c["name"] for c in s["cards"]]),
        None
    )

    if high_synergy and low_synergy:
        # High synergy shares keywords, should have higher score
        assert high_synergy["synergy_score"] > low_synergy["synergy_score"]
