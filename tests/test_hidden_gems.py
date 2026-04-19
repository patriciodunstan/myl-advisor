"""Tests for hidden gems finder service."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.hidden_gems_finder import (
    find_hidden_gems,
    _get_rarity_bonus,
    _generate_reason,
)
from app.shared_models import Edition, Race, Type, Rarity, Card


def test_get_rarity_bonus():
    """Test rarity bonus calculation."""
    assert _get_rarity_bonus("comun") == 1.5
    assert _get_rarity_bonus("incomun") == 1.3
    assert _get_rarity_bonus("rara") == 1.1
    assert _get_rarity_bonus("epica") == 0.9
    assert _get_rarity_bonus("legendaria") == 0.7
    assert _get_rarity_bonus(None) == 1.0
    assert _get_rarity_bonus("unknown") == 1.0


def test_generate_reason():
    """Test reason generation for hidden gems."""
    # High score gem
    reason = _generate_reason(4, "Común", 2, 85)
    assert "4 keywords" in reason
    assert "Común" in reason
    assert "coste 2" in reason
    assert "extremadamente eficiente" in reason

    # Medium score gem
    reason = _generate_reason(3, "Incomún", 4, 65)
    assert "3 keywords" in reason
    assert "Incomún" in reason
    assert "coste 4" in reason
    assert "eficiente" in reason

    # Low score gem
    reason = _generate_reason(2, "Rara", 6, 30)
    assert "2 keywords" in reason
    assert "moderadamente eficiente" in reason


@pytest.mark.asyncio
async def test_find_hidden_gems_basic(test_session: AsyncSession):
    """Test finding hidden gems in a race."""
    # Create related entities
    edition = Edition(id=50, slug="test5", title="Test Edition 5")
    race = Race(id=50, slug="test_race5", name="Test Race 5")
    type_obj = Type(id=50, slug="aliado", name="Aliado")
    rarity_comun = Rarity(id=50, slug="comun", name="Común")

    test_session.add(edition)
    test_session.add(race)
    test_session.add(type_obj)
    test_session.add(rarity_comun)
    await test_session.flush()

    # Create cards with varying keyword counts
    # High keyword count gem (should rank high)
    gem_card = Card(
        edid="GEM001",
        slug="gem-card",
        name="Gem Card",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity_comun.id,
        cost=2,
        damage=2,
        ability="Furia. Destruir un aliado enemigo. Robar una carta. Indestructible.",
        keywords="Furia, Destruir, Robar, Indestructible",
    )
    test_session.add(gem_card)

    # Low keyword count card (should rank low)
    low_gem = Card(
        edid="GEM002",
        slug="low-gem",
        name="Low Gem",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity_comun.id,
        cost=1,
        damage=1,
        ability="Furia.",
        keywords="Furia",
    )
    test_session.add(low_gem)

    await test_session.commit()

    # Find hidden gems
    result = await find_hidden_gems(
        test_session,
        race_slug="test_race5",
        format_type="racial_edicion",
        min_keywords=1,
        limit=10,
    )

    assert result["meta"]["gems_found"] >= 1
    assert result["meta"]["cards_analyzed"] >= 2

    # Check that gem card has better score than low gem
    gem_card_result = next(
        (g for g in result["hidden_gems"] if g["card"]["name"] == "Gem Card"),
        None
    )
    low_gem_result = next(
        (g for g in result["hidden_gems"] if g["card"]["name"] == "Low Gem"),
        None
    )

    if gem_card_result and low_gem_result:
        # Gem card has more keywords and should have higher score
        assert gem_card_result["gem_score"] > low_gem_result["gem_score"]
        assert gem_card_result["keyword_count"] == 4
        assert low_gem_result["keyword_count"] == 1


@pytest.mark.asyncio
async def test_find_hidden_gems_race_not_found(test_session: AsyncSession):
    """Test finding hidden gems for non-existent race."""
    result = await find_hidden_gems(
        test_session,
        race_slug="nonexistent_race",
        format_type="racial_edicion",
    )

    assert result["meta"]["gems_found"] == 0
    assert "error" in result["meta"]
    assert len(result["hidden_gems"]) == 0


@pytest.mark.asyncio
async def test_find_hidden_gems_min_keywords_filter(test_session: AsyncSession):
    """Test filtering by minimum keyword count."""
    # Create related entities
    edition = Edition(id=60, slug="test6", title="Test Edition 6")
    race = Race(id=60, slug="test_race6", name="Test Race 6")
    type_obj = Type(id=60, slug="aliado", name="Aliado")
    rarity = Rarity(id=60, slug="comun", name="Común")

    test_session.add(edition)
    test_session.add(race)
    test_session.add(type_obj)
    test_session.add(rarity)
    await test_session.flush()

    # Create card with 1 keyword
    low_keywords = Card(
        edid="GEM010",
        slug="low-keywords",
        name="Low Keywords",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity.id,
        cost=1,
        damage=1,
        ability="Furia.",
        keywords="Furia",
    )
    test_session.add(low_keywords)

    # Create card with 3 keywords
    medium_keywords = Card(
        edid="GEM011",
        slug="medium-keywords",
        name="Medium Keywords",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity.id,
        cost=2,
        damage=2,
        ability="Furia. Destruir un aliado. Robar una carta.",
        keywords="Furia, Destruir, Robar",
    )
    test_session.add(medium_keywords)

    await test_session.commit()

    # Find gems with min_keywords=2 (should exclude low_keywords)
    result = await find_hidden_gems(
        test_session,
        race_slug="test_race6",
        format_type="racial_edicion",
        min_keywords=2,
        limit=10,
    )

    assert result["meta"]["gems_found"] >= 1
    for gem in result["hidden_gems"]:
        assert gem["keyword_count"] >= 2

    # Low keywords should not be in results
    low_keywords_found = any(
        gem["card"]["name"] == "Low Keywords"
        for gem in result["hidden_gems"]
    )
    assert not low_keywords_found


@pytest.mark.asyncio
async def test_find_hidden_gems_max_cost_filter(test_session: AsyncSession):
    """Test filtering by maximum cost."""
    # Create related entities
    edition = Edition(id=70, slug="test7", title="Test Edition 7")
    race = Race(id=70, slug="test_race7", name="Test Race 7")
    type_obj = Type(id=70, slug="aliado", name="Aliado")
    rarity = Rarity(id=70, slug="comun", name="Común")

    test_session.add(edition)
    test_session.add(race)
    test_session.add(type_obj)
    test_session.add(rarity)
    await test_session.flush()

    # Create cheap gem
    cheap_gem = Card(
        edid="GEM020",
        slug="cheap-gem",
        name="Cheap Gem",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity.id,
        cost=2,
        damage=2,
        ability="Furia. Destruir. Robar.",
        keywords="Furia, Destruir, Robar",
    )
    test_session.add(cheap_gem)

    # Create expensive gem
    expensive_gem = Card(
        edid="GEM021",
        slug="expensive-gem",
        name="Expensive Gem",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity.id,
        cost=8,
        damage=5,
        ability="Furia. Destruir. Robar.",
        keywords="Furia, Destruir, Robar",
    )
    test_session.add(expensive_gem)

    await test_session.commit()

    # Find gems with max_cost=3 (should exclude expensive)
    result = await find_hidden_gems(
        test_session,
        race_slug="test_race7",
        format_type="racial_edicion",
        max_cost=3,
        min_keywords=2,
        limit=10,
    )

    # Cheap gem should be in results
    cheap_found = any(
        gem["card"]["name"] == "Cheap Gem"
        for gem in result["hidden_gems"]
    )
    assert cheap_found

    # Expensive gem should not be in results
    expensive_found = any(
        gem["card"]["name"] == "Expensive Gem"
        for gem in result["hidden_gems"]
    )
    assert not expensive_found


@pytest.mark.asyncio
async def test_find_hidden_gems_filtered_by_banlist(test_session: AsyncSession):
    """Test that banned cards are filtered out."""
    from app.shared_models import Banlist

    # Create related entities
    edition = Edition(id=80, slug="test8", title="Test Edition 8")
    race = Race(id=80, slug="test_race8", name="Test Race 8")
    type_obj = Type(id=80, slug="aliado", name="Aliado")
    rarity = Rarity(id=80, slug="comun", name="Común")

    test_session.add(edition)
    test_session.add(race)
    test_session.add(type_obj)
    test_session.add(rarity)
    await test_session.flush()

    # Create banned gem
    banned_gem = Card(
        edid="GEM030",
        slug="banned-gem",
        name="Banned Gem",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity.id,
        cost=2,
        damage=2,
        ability="Furia. Destruir. Robar.",
        keywords="Furia, Destruir, Robar",
    )
    test_session.add(banned_gem)

    ban_entry = Banlist(
        card_name="Banned Gem",
        format="racial_edicion",
        restriction="prohibida"
    )
    test_session.add(ban_entry)

    await test_session.commit()

    # Find gems
    result = await find_hidden_gems(
        test_session,
        race_slug="test_race8",
        format_type="racial_edicion",
        min_keywords=2,
        limit=10,
    )

    # Banned gem should not be in results
    banned_found = any(
        gem["card"]["name"] == "Banned Gem"
        for gem in result["hidden_gems"]
    )
    assert not banned_found


@pytest.mark.asyncio
async def test_find_hidden_gems_rarity_bonus(test_session: AsyncSession):
    """Test that rarity bonus is applied correctly."""
    # Create related entities
    edition = Edition(id=90, slug="test9", title="Test Edition 9")
    race = Race(id=90, slug="test_race9", name="Test Race 9")
    type_obj = Type(id=90, slug="aliado", name="Aliado")
    rarity_comun = Rarity(id=90, slug="comun", name="Común")
    rarity_legendaria = Rarity(id=91, slug="legendaria", name="Legendaria")

    test_session.add(edition)
    test_session.add(race)
    test_session.add(type_obj)
    test_session.add(rarity_comun)
    test_session.add(rarity_legendaria)
    await test_session.flush()

    # Create common gem (should have higher score)
    common_gem = Card(
        edid="GEM040",
        slug="common-gem",
        name="Common Gem",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity_comun.id,
        cost=3,
        damage=2,
        ability="Furia. Destruir. Robar.",
        keywords="Furia, Destruir, Robar",
    )
    test_session.add(common_gem)

    # Create legendary gem with same keywords and cost (should have lower score)
    legendary_gem = Card(
        edid="GEM041",
        slug="legendary-gem",
        name="Legendary Gem",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity_legendaria.id,
        cost=3,
        damage=5,
        ability="Furia. Destruir. Robar.",
        keywords="Furia, Destruir, Robar",
    )
    test_session.add(legendary_gem)

    await test_session.commit()

    # Find gems
    result = await find_hidden_gems(
        test_session,
        race_slug="test_race9",
        format_type="racial_edicion",
        min_keywords=2,
        limit=10,
    )

    # Both should be found
    common_result = next(
        (g for g in result["hidden_gems"] if g["card"]["name"] == "Common Gem"),
        None
    )
    legendary_result = next(
        (g for g in result["hidden_gems"] if g["card"]["name"] == "Legendary Gem"),
        None
    )

    if common_result and legendary_result:
        # Common should have higher score due to rarity bonus
        assert common_result["gem_score"] > legendary_result["gem_score"]


@pytest.mark.asyncio
async def test_find_hidden_gems_sorted_by_score(test_session: AsyncSession):
    """Test that gems are sorted by score (highest first)."""
    # Create related entities
    edition = Edition(id=100, slug="test10", title="Test Edition 10")
    race = Race(id=100, slug="test_race10", name="Test Race 10")
    type_obj = Type(id=100, slug="aliado", name="Aliado")
    rarity = Rarity(id=100, slug="comun", name="Común")

    test_session.add(edition)
    test_session.add(race)
    test_session.add(type_obj)
    test_session.add(rarity)
    await test_session.flush()

    # Create multiple gems
    gem1 = Card(
        edid="GEM050",
        slug="gem1",
        name="Gem 1",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity.id,
        cost=2,
        ability="Furia. Destruir.",
        keywords="Furia, Destruir",
    )
    test_session.add(gem1)

    gem2 = Card(
        edid="GEM051",
        slug="gem2",
        name="Gem 2",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity.id,
        cost=1,
        ability="Furia. Destruir. Robar.",
        keywords="Furia, Destruir, Robar",
    )
    test_session.add(gem2)

    gem3 = Card(
        edid="GEM052",
        slug="gem3",
        name="Gem 3",
        edition_id=edition.id,
        race_id=race.id,
        type_id=type_obj.id,
        rarity_id=rarity.id,
        cost=3,
        ability="Furia.",
        keywords="Furia",
    )
    test_session.add(gem3)

    await test_session.commit()

    # Find gems
    result = await find_hidden_gems(
        test_session,
        race_slug="test_race10",
        format_type="racial_edicion",
        min_keywords=1,
        limit=10,
    )

    if len(result["hidden_gems"]) >= 2:
        scores = [g["gem_score"] for g in result["hidden_gems"]]
        # Check that scores are sorted descending
        assert scores == sorted(scores, reverse=True)
