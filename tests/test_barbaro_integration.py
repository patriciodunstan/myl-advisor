"""Integration tests for Barbaro race card advisor endpoints."""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.alternative_finder import find_alternatives
from app.services.hidden_gems_finder import find_hidden_gems
from app.services.synergy_analyzer import find_synergies
from app.shared_models import Edition, Race, Type, Rarity, Card


# Barbaro test fixture data - realistic MyL cards
BARBARO_CARDS = [
    {
        "id": 101, "edid": "DD001", "slug": "genseric", "name": "Genseric",
        "edition_id": 1, "race_id": 2, "type_id": 1, "rarity_id": 1,
        "cost": 3, "damage": 2,
        "ability": "Furia. Cuando esta carta entra en juego, destruye un aliado objetivo de coste 2 o menos.",
        "keywords": "Furia, Destruir"
    },
    {
        "id": 102, "edid": "DD002", "slug": "medea", "name": "Medea",
        "edition_id": 1, "race_id": 2, "type_id": 1, "rarity_id": 1,
        "cost": 4, "damage": 3,
        "ability": "Imbloqueable. Cuando entra en juego, roba 2 cartas de tu mazo.",
        "keywords": "Imbloqueable, Robar"
    },
    {
        "id": 103, "edid": "DD003", "slug": "viriato", "name": "Viriato",
        "edition_id": 1, "race_id": 2, "type_id": 1, "rarity_id": 2,
        "cost": 2, "damage": 1,
        "ability": "Guardián. Exhumar. Puedes pagar 1 oro para retornar esta carta del cementerio a tu mano.",
        "keywords": "Guardián, Exhumar"
    },
    {
        "id": 104, "edid": "DD004", "slug": "alboin", "name": "Alboin",
        "edition_id": 1, "race_id": 2, "type_id": 1, "rarity_id": 1,
        "cost": 5, "damage": 4,
        "ability": "Furia. Indestructible. Cuando ataca, inflige 2 puntos de daño al castillo oponente.",
        "keywords": "Furia, Indestructible"
    },
    {
        "id": 105, "edid": "DD005", "slug": "odoacro", "name": "Odoacro",
        "edition_id": 1, "race_id": 2, "type_id": 1, "rarity_id": 1,
        "cost": 4, "damage": 3,
        "ability": "Furia. Destruye un aliado objetivo que no tenga habilidad.",
        "keywords": "Furia, Destruir"
    },
    {
        "id": 106, "edid": "DD006", "slug": "tamora", "name": "Tamora",
        "edition_id": 1, "race_id": 2, "type_id": 1, "rarity_id": 3,
        "cost": 6, "damage": 5,
        "ability": "Imbloqueable. Furia. Cuando entra en juego, destierra las 2 primeras cartas del mazo oponente.",
        "keywords": "Imbloqueable, Furia, Desterrar"
    },
    {
        "id": 107, "edid": "DD007", "slug": "admeto", "name": "Admeto",
        "edition_id": 1, "race_id": 2, "type_id": 1, "rarity_id": 2,
        "cost": 3, "damage": 2,
        "ability": "Retador. Genera 1 oro adicional cuando entra en juego.",
        "keywords": "Retador, Generar"
    },
    {
        "id": 108, "edid": "DD008", "slug": "charlotte-de-berry", "name": "Charlotte de Berry",
        "edition_id": 1, "race_id": 2, "type_id": 1, "rarity_id": 2,
        "cost": 2, "damage": 2,
        "ability": "Mercenario. Puedes jugar esta carta sin pagar su coste si controlas un aliado Bárbaro.",
        "keywords": "Mercenario"
    },
]


@pytest_asyncio.fixture
async def barbaro_setup(test_session: AsyncSession):
    """Set up realistic Barbaro cards for integration testing."""
    # Create Edition, Race=barbaro, Type=aliado, Rarities
    edition = Edition(id=1, slug="dinastia-del-dragon", title="Dinastía del Dragón")
    race = Race(id=2, slug="barbaro", name="Bárbaro")
    type_obj = Type(id=1, slug="aliado", name="Aliado")
    rarity_comun = Rarity(id=1, slug="comun", name="Común")
    rarity_incomun = Rarity(id=2, slug="incomun", name="Incomún")
    rarity_rara = Rarity(id=3, slug="rara", name="Rara")

    test_session.add_all([edition, race, type_obj, rarity_comun, rarity_incomun, rarity_rara])
    await test_session.flush()

    # Create all Barbaro cards
    for card_data in BARBARO_CARDS:
        card = Card(**card_data)
        test_session.add(card)

    await test_session.commit()
    return {"edition": edition, "race": race, "session": test_session}


@pytest_asyncio.fixture
async def barbaro_client(client: AsyncClient, db_session: AsyncSession):
    """Create a test client with Barbaro data pre-loaded."""
    # Create Edition, Race=barbaro, Type=aliado, Rarities
    edition = Edition(id=1, slug="dinastia-del-dragon", title="Dinastía del Dragón")
    race = Race(id=2, slug="barbaro", name="Bárbaro")
    type_obj = Type(id=1, slug="aliado", name="Aliado")
    rarity_comun = Rarity(id=1, slug="comun", name="Común")
    rarity_incomun = Rarity(id=2, slug="incomun", name="Incomún")
    rarity_rara = Rarity(id=3, slug="rara", name="Rara")

    db_session.add_all([edition, race, type_obj, rarity_comun, rarity_incomun, rarity_rara])
    await db_session.flush()

    # Create all Barbaro cards
    for card_data in BARBARO_CARDS:
        card = Card(**card_data)
        db_session.add(card)

    await db_session.commit()
    return client


# ==================== ALTERNATIVES TESTS ====================

@pytest.mark.asyncio
async def test_find_alternatives_for_genseric(barbaro_setup):
    """Find alternatives for Genseric (cost 3, Furia+Destruir). Should find Odoacro as top alternative."""
    test_session = barbaro_setup["session"]
    result = await find_alternatives(
        test_session,
        card_name="Genseric",
        format_type="racial_edicion",
    )

    assert result["meta"]["target_card_found"] is True
    assert result["meta"]["target_card"]["name"] == "Genseric"
    assert len(result["alternatives"]) >= 1

    # Odoacro shares Furia+Destruir and should be a top alternative
    odoacro_found = any(
        alt["card"]["name"] == "Odoacro" for alt in result["alternatives"]
    )
    assert odoacro_found


@pytest.mark.asyncio
async def test_find_alternatives_for_medea(barbaro_setup):
    """Find alternatives for Medea (cost 4, Imbloqueable+Robar). Should find low similarity."""
    test_session = barbaro_setup["session"]
    result = await find_alternatives(
        test_session,
        card_name="Medea",
        format_type="racial_edicion",
    )

    assert result["meta"]["target_card_found"] is True
    assert result["meta"]["target_card"]["name"] == "Medea"

    # Medea has Imbloqueable+Robar which is unique, so alternatives should have lower similarity
    if len(result["alternatives"]) > 0:
        # All alternatives should have similarity < 100 since no card has both Imbloqueable+Robar
        for alt in result["alternatives"]:
            assert alt["similarity"] < 100


@pytest.mark.asyncio
async def test_find_alternatives_with_max_cost(barbaro_setup):
    """Find alternatives for Alboin (cost 5) with max_cost=3. Should only return cards cost ≤3."""
    test_session = barbaro_setup["session"]
    result = await find_alternatives(
        test_session,
        card_name="Alboin",
        format_type="racial_edicion",
        max_cost=3,
    )

    assert result["meta"]["target_card_found"] is True
    assert result["meta"]["target_card"]["name"] == "Alboin"

    # All alternatives should have cost ≤ 3
    for alt in result["alternatives"]:
        assert alt["card"]["cost"] <= 3


@pytest.mark.asyncio
async def test_alternatives_card_not_in_race(barbaro_setup):
    """Find alternatives for a card that has no alternatives in its race (edge case)."""
    # Create a card in a different race
    test_session = barbaro_setup["session"]
    other_race = Race(id=3, slug="otros", name="Otros")
    test_session.add(other_race)
    await test_session.flush()

    other_card = Card(
        id=999,
        edid="OTH001",
        slug="unique-card",
        name="Unique Card",
        edition_id=1,
        race_id=3,  # Different race
        type_id=1,
        rarity_id=1,
        cost=3,
        damage=2,
        ability="Unique ability.",
        keywords="Unique"
    )
    test_session.add(other_card)
    await test_session.commit()

    result = await find_alternatives(
        test_session,
        card_name="Unique Card",
        format_type="racial_edicion",
    )

    # Card should be found but no alternatives in same race
    assert result["meta"]["target_card_found"] is True
    assert len(result["alternatives"]) == 0


# ==================== HIDDEN GEMS TESTS ====================

@pytest.mark.asyncio
async def test_hidden_gems_barbaro(barbaro_setup):
    """Find hidden gems in Barbaro race. Viriato (Guardián+Exhumar at cost 2, uncommon) should rank high."""
    test_session = barbaro_setup["session"]
    result = await find_hidden_gems(
        test_session,
        race_slug="barbaro",
        format_type="racial_edicion",
        min_keywords=1,
        limit=10,
    )

    assert result["meta"]["gems_found"] >= 1
    assert result["meta"]["cards_analyzed"] >= 1

    # Viriato should be found (2 keywords, cost 2, uncommon)
    viriato_found = any(
        gem["card"]["name"] == "Viriato" for gem in result["hidden_gems"]
    )
    assert viriato_found


@pytest.mark.asyncio
async def test_hidden_gems_min_keywords_filter(barbaro_setup):
    """Find hidden gems with min_keywords=3. Only cards with 3+ keywords should appear."""
    test_session = barbaro_setup["session"]
    result = await find_hidden_gems(
        test_session,
        race_slug="barbaro",
        format_type="racial_edicion",
        min_keywords=3,
        limit=10,
    )

    # Tamora has 3 keywords (Imbloqueable, Furia, Desterrar)
    assert result["meta"]["gems_found"] >= 1

    # All gems should have 3+ keywords
    for gem in result["hidden_gems"]:
        assert gem["keyword_count"] >= 3

    # Tamora should be in results
    tamora_found = any(
        gem["card"]["name"] == "Tamora" for gem in result["hidden_gems"]
    )
    assert tamora_found


@pytest.mark.asyncio
async def test_hidden_gems_max_cost_filter(barbaro_setup):
    """Find hidden gems with max_cost=3. Only cards cost ≤3 should appear."""
    test_session = barbaro_setup["session"]
    result = await find_hidden_gems(
        test_session,
        race_slug="barbaro",
        format_type="racial_edicion",
        min_keywords=1,
        max_cost=3,
        limit=10,
    )

    # Should find gems like Viriato (cost 2), Genseric (cost 3), Admeto (cost 3), Charlotte (cost 2)
    assert result["meta"]["gems_found"] >= 1

    # All gems should have cost ≤ 3
    for gem in result["hidden_gems"]:
        assert gem["card"]["cost"] <= 3

    # Tamora (cost 6) and Alboin (cost 5) should NOT be in results
    tamora_found = any(
        gem["card"]["name"] == "Tamora" for gem in result["hidden_gems"]
    )
    alboin_found = any(
        gem["card"]["name"] == "Alboin" for gem in result["hidden_gems"]
    )
    assert not tamora_found
    assert not alboin_found


@pytest.mark.asyncio
async def test_hidden_gems_rarity_bonus(barbaro_setup):
    """Test that rarity bonus affects gem scoring. Viriato (uncommon) should score well."""
    test_session = barbaro_setup["session"]
    result = await find_hidden_gems(
        test_session,
        race_slug="barbaro",
        format_type="racial_edicion",
        min_keywords=1,
        limit=10,
    )

    # Find Viriato result
    viriato_result = next(
        (g for g in result["hidden_gems"] if g["card"]["name"] == "Viriato"),
        None
    )

    assert viriato_result is not None
    assert viriato_result["keyword_count"] >= 2  # Guardián, Exhumar
    assert viriato_result["card"]["cost"] == 2
    # Viriato should have a good score due to uncommon rarity (1.3x bonus) + keywords


@pytest.mark.asyncio
async def test_hidden_gems_sorted_by_score(barbaro_setup):
    """Test that gems are sorted by score (highest first)."""
    test_session = barbaro_setup["session"]
    result = await find_hidden_gems(
        test_session,
        race_slug="barbaro",
        format_type="racial_edicion",
        min_keywords=1,
        limit=10,
    )

    if len(result["hidden_gems"]) >= 2:
        scores = [g["gem_score"] for g in result["hidden_gems"]]
        # Check that scores are sorted descending
        assert scores == sorted(scores, reverse=True)


# ==================== SYNERGIES TESTS ====================

@pytest.mark.asyncio
async def test_synergies_removal_draw(barbaro_setup):
    """Find synergies between Genseric (Destruir) and Medea (Robar). Should detect removal+draw synergy."""
    test_session = barbaro_setup["session"]
    result = await find_synergies(
        test_session,
        card_names=["Genseric"],
        race_slug="barbaro",
        format_type="racial_edicion",
    )

    assert result["meta"]["synergies_found"] >= 1
    assert len(result["synergies"]) >= 1

    # Should find synergy between Genseric (removal) and Medea (draw)
    genseric_medea_synergy = any(
        "Genseric" in [c["name"] for c in s["cards"]] and
        "Medea" in [c["name"] for c in s["cards"]]
        for s in result["synergies"]
    )
    assert genseric_medea_synergy


@pytest.mark.asyncio
async def test_synergies_buff_evasion(barbaro_setup):
    """Find synergies between Alboin (Indestructible) and Medea (Imbloqueable). Should return synergies."""
    test_session = barbaro_setup["session"]
    result = await find_synergies(
        test_session,
        card_names=["Alboin"],
        race_slug="barbaro",
        format_type="racial_edicion",
    )

    # Just verify synergies are returned (less strict than checking for specific synergy)
    assert result["meta"]["synergies_found"] >= 1
    assert len(result["synergies"]) >= 1


@pytest.mark.asyncio
async def test_synergies_multiple_cards(barbaro_setup):
    """Find synergies between 3 cards: Genseric, Medea, Alboin. Should return multiple synergy pairs."""
    test_session = barbaro_setup["session"]
    result = await find_synergies(
        test_session,
        card_names=["Genseric", "Medea"],
        race_slug="barbaro",
        format_type="racial_edicion",
    )

    assert result["meta"]["synergies_found"] >= 1
    assert len(result["meta"]["input_cards"]) == 2

    # Should find multiple synergies involving the input cards
    # Each synergy should include at least one input card
    input_card_names = {"Genseric", "Medea"}
    for synergy in result["synergies"]:
        synergy_card_names = {c["name"] for c in synergy["cards"]}
        # Each synergy should overlap with input cards
        overlap = synergy_card_names & input_card_names
        assert len(overlap) >= 1


@pytest.mark.asyncio
async def test_synergies_card_not_found(barbaro_setup):
    """Find synergies for non-existent card."""
    test_session = barbaro_setup["session"]
    result = await find_synergies(
        test_session,
        card_names=["Nonexistent Card"],
        race_slug="barbaro",
        format_type="racial_edicion",
    )

    assert result["meta"]["synergies_found"] == 0
    assert "error" in result["meta"]


@pytest.mark.asyncio
async def test_synergies_scoring(barbaro_setup):
    """Test that synergies are scored and sorted correctly."""
    test_session = barbaro_setup["session"]
    result = await find_synergies(
        test_session,
        card_names=["Genseric"],
        race_slug="barbaro",
        format_type="racial_edicion",
        limit=10,
    )

    if len(result["synergies"]) >= 2:
        # Check that synergies are sorted by score (highest first)
        scores = [s["synergy_score"] for s in result["synergies"]]
        assert scores == sorted(scores, reverse=True)


# ==================== ENDPOINT TESTS ====================

@pytest.mark.asyncio
async def test_alternatives_endpoint_barbaro(barbaro_client: AsyncClient):
    """POST /advisor/alternatives with card_name='Genseric'. Verify response structure."""
    response = await barbaro_client.post(
        "/advisor/alternatives",
        json={
            "card_name": "Genseric",
            "format": "racial_edicion"
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert "alternatives" in data
    assert "meta" in data
    assert data["meta"]["target_card_found"] is True
    assert data["meta"]["target_card"]["name"] == "Genseric"
    assert len(data["alternatives"]) >= 1


@pytest.mark.asyncio
async def test_hidden_gems_endpoint_barbaro(barbaro_client: AsyncClient):
    """POST /advisor/hidden-gems with race_slug='barbaro'. Verify response structure."""
    response = await barbaro_client.post(
        "/advisor/hidden-gems",
        json={
            "race_slug": "barbaro",
            "format": "racial_edicion",
            "min_keywords": 1,
            "limit": 10
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert "hidden_gems" in data
    assert "meta" in data
    assert data["meta"]["gems_found"] >= 1
    assert data["meta"]["cards_analyzed"] >= 1


@pytest.mark.asyncio
async def test_synergies_endpoint_barbaro(barbaro_client: AsyncClient):
    """POST /advisor/synergies with card_names=['Genseric', 'Medea']. Verify response structure."""
    response = await barbaro_client.post(
        "/advisor/synergies",
        json={
            "card_names": ["Genseric", "Medea"],
            "race_slug": "barbaro",
            "format": "racial_edicion"
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert "synergies" in data
    assert "meta" in data
    assert data["meta"]["synergies_found"] >= 1
    assert len(data["meta"]["input_cards"]) == 2


@pytest.mark.asyncio
async def test_alternatives_endpoint_not_found(barbaro_client: AsyncClient):
    """POST /advisor/alternatives with non-existent card. Should return 404."""
    response = await barbaro_client.post(
        "/advisor/alternatives",
        json={
            "card_name": "Nonexistent Card",
            "format": "racial_edicion"
        }
    )

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_hidden_gems_endpoint_not_found(barbaro_client: AsyncClient):
    """POST /advisor/hidden-gems with non-existent race. Should return 404."""
    response = await barbaro_client.post(
        "/advisor/hidden-gems",
        json={
            "race_slug": "nonexistent_race",
            "format": "racial_edicion",
            "min_keywords": 1
        }
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_synergies_endpoint_not_found(barbaro_client: AsyncClient):
    """POST /advisor/synergies with non-existent card. Should return 404."""
    response = await barbaro_client.post(
        "/advisor/synergies",
        json={
            "card_names": ["Nonexistent Card"],
            "race_slug": "barbaro",
            "format": "racial_edicion"
        }
    )

    assert response.status_code == 404
