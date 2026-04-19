"""Synergy Analyzer Service - Find cards that work well together."""
import logging
from typing import List, Optional, Set, Dict, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.card_reader import get_card_by_name, get_cards_by_race_and_cost, check_banlist
from app.services.alternative_finder import extract_keywords


logger = logging.getLogger(__name__)


# Define synergy categories and their keyword groups
SYNERGY_DEFINITIONS = {
    "combo": {
        "REMOVAL": {"Destruir", "Anular", "Desterrar"},
        "DRAW": {"Robar", "Mazo", "Mano"},
        "BUFF": {"Vida", "Armadura", "Daño"},
        "EVASION": {"Imbloqueable", "Vuelo", "Errante"},
        "SUMMON": {"Exhumar", "Generar", "Cementerio"},
        "PROTECTION": {"Indestructible", "Inmunidad", "Guardián"},
        "RESOURCE": {"Oro Inicial", "Generar"},
        "HIGH_COST": None,  # Computed from card cost
    }
}


def _get_synergy_category(keywords: Set[str]) -> str:
    """Determine the primary synergy category based on keywords."""
    if not keywords:
        return "other"

    # Check each category
    for keyword in keywords:
        if keyword in SYNERGY_DEFINITIONS["combo"]["REMOVAL"]:
            return "removal"
        elif keyword in SYNERGY_DEFINITIONS["combo"]["DRAW"]:
            return "draw"
        elif keyword in SYNERGY_DEFINITIONS["combo"]["BUFF"]:
            return "buff"
        elif keyword in SYNERGY_DEFINITIONS["combo"]["EVASION"]:
            return "evasion"
        elif keyword in SYNERGY_DEFINITIONS["combo"]["RESOURCE"]:
            return "resource"
        elif keyword in SYNERGY_DEFINITIONS["combo"]["SUMMON"]:
            return "summon"
        elif keyword in SYNERGY_DEFINITIONS["combo"]["PROTECTION"]:
            return "protection"

    return "other"


def _check_synergy(category_a: str, category_b: str) -> Tuple[bool, str, str]:
    """Check if two categories have synergy and return the type and explanation."""
    synergy_pairs = [
        ("removal", "draw", "combo", "Remueve amenazas mientras roba cartas para mantener ventaja"),
        ("removal", "buff", "combo", "Remueve amenazas y prepara tus criaturas para el combate"),
        ("removal", "evasion", "combo", "Remueve bloqueadores mientras atacas con criaturas imblocables"),
        ("buff", "evasion", "combo", "Aumenta el daño de criaturas que no pueden ser bloqueadas"),
        ("summon", "protection", "engine", "Invoca criaturas recursivamente que son difíciles de eliminar"),
        ("resource", "summon", "engine", "Genera recursos para invocar criaturas más rápido"),
        ("resource", "buff", "engine", "Genera recursos y potencia tus criaturas"),
        ("buff", "protection", "protection", "Protege y potencia tu criatura clave"),
        ("draw", "summon", "engine", "Roba cartas para encontrar más criaturas y mantener el ritmo"),
        ("draw", "protection", "protection", "Roba cartas mientras proteges tu campo"),
    ]

    for cat1, cat2, synergy_type, explanation in synergy_pairs:
        if (category_a == cat1 and category_b == cat2) or (category_a == cat2 and category_b == cat1):
            return True, synergy_type, explanation

    return False, "", ""


def _calculate_synergy_score(
    card_a: dict,
    card_b: dict,
    synergy_type: str,
) -> int:
    """Calculate synergy score between two cards (0-100)."""
    base_score = 50  # Base score for any synergy

    # Bonus for shared keywords
    keywords_a = extract_keywords(card_a.get("ability"))
    keywords_b = extract_keywords(card_b.get("ability"))
    shared_keywords = keywords_a & keywords_b

    shared_bonus = len(shared_keywords) * 10  # +10 per shared keyword

    # Bonus based on synergy type
    synergy_bonus = {
        "combo": 20,
        "engine": 15,
        "protection": 10,
    }.get(synergy_type, 0)

    # Bonus for cost efficiency (lower is better)
    cost_a = card_a.get("cost") or 0
    cost_b = card_b.get("cost") or 0
    avg_cost = (cost_a + cost_b) / 2

    if avg_cost <= 3:
        cost_bonus = 10
    elif avg_cost <= 5:
        cost_bonus = 5
    else:
        cost_bonus = 0

    total_score = base_score + shared_bonus + synergy_bonus + cost_bonus

    # Cap at 100
    return min(total_score, 100)


async def find_synergies(
    session: AsyncSession,
    card_names: List[str],
    race_slug: Optional[str] = None,
    format_type: str = "racial_edicion",
    limit: int = 10,
) -> dict:
    """
    Find cards that work well together based on keyword/effect combinations.

    Process:
    1. Get all cards by name from DB
    2. For each card, extract keywords
    3. Find complementary effects based on synergy definitions
    4. Query DB for cards of same race that provide complementary effects
    5. Score synergies and return top results
    """
    logger.info(
        "find_synergies | card_names=%r race=%r format=%r limit=%d",
        card_names, race_slug, format_type, limit
    )

    # Step 1: Get all input cards
    input_cards = []
    for card_name in card_names:
        card = await get_card_by_name(session, card_name)
        if card:
            input_cards.append(card)
        else:
            logger.warning("find_synergies | card not found: %r", card_name)

    if not input_cards:
        return {
            "synergies": [],
            "meta": {
                "input_cards": card_names,
                "synergies_found": 0,
                "format": format_type,
                "error": "No input cards found in database"
            }
        }

    # Get race from input cards if not specified
    if not race_slug:
        race_slug = input_cards[0].get("race_slug")
        logger.info("find_synergies | using race from first card: %s", race_slug)

    if not race_slug:
        return {
            "synergies": [],
            "meta": {
                "input_cards": card_names,
                "synergies_found": 0,
                "format": format_type,
                "error": "No race specified and cards have no race"
            }
        }

    # Step 2: Extract keywords from input cards
    input_card_keywords = {}
    input_card_categories = {}
    for card in input_cards:
        keywords = extract_keywords(card.get("ability"))
        input_card_keywords[card["name"]] = keywords
        input_card_categories[card["name"]] = _get_synergy_category(keywords)

    logger.debug("Input card categories: %s", input_card_categories)

    # Step 3: Get candidate cards from same race
    candidate_cards = await get_cards_by_race_and_cost(
        session=session,
        race_slug=race_slug,
        max_cost=None,  # No cost limit for synergies
        exclude_card_name=None,  # Allow same cards
        limit=100  # Get more candidates
    )

    # Filter out input cards from candidates
    candidate_cards = [
        c for c in candidate_cards
        if c["name"] not in [card["name"] for card in input_cards]
    ]

    logger.info("Found %d candidate cards", len(candidate_cards))

    # Step 4: Check banlist and filter
    filtered_candidates = []
    for candidate in candidate_cards:
        ban_status = await check_banlist(session, candidate["name"], format_type)
        if not ban_status:
            filtered_candidates.append(candidate)
        else:
            logger.debug("Skipping banned card: %s", candidate["name"])

    logger.info("After banlist filter: %d candidates", len(filtered_candidates))

    # Step 5: Find synergies
    synergies = []

    for candidate in filtered_candidates:
        candidate_keywords = extract_keywords(candidate.get("ability"))
        candidate_category = _get_synergy_category(candidate_keywords)

        # Check synergy with each input card
        for input_card in input_cards:
            input_category = input_card_categories[input_card["name"]]
            has_synergy, synergy_type, explanation = _check_synergy(
                input_category,
                candidate_category
            )

            if has_synergy:
                # Calculate score
                score = _calculate_synergy_score(input_card, candidate, synergy_type)

                # Check if we already have this pair
                existing_pair = None
                for existing in synergies:
                    card_names_in_pair = [c["name"] for c in existing["cards"]]
                    if (input_card["name"] in card_names_in_pair and
                        candidate["name"] in card_names_in_pair):
                        existing_pair = existing
                        break

                if existing_pair:
                    # Update if this synergy has a higher score
                    if score > existing_pair["synergy_score"]:
                        existing_pair["synergy_score"] = score
                        existing_pair["synergy_type"] = synergy_type
                        existing_pair["explanation"] = explanation
                else:
                    # Create new synergy pair
                    card_names_in_pair = [input_card["name"], candidate["name"]]
                    # Sort for consistency
                    card_names_in_pair.sort()

                    # Get cards
                    pair_cards = []
                    if card_names_in_pair[0] == input_card["name"]:
                        pair_cards.append(input_card)
                    else:
                        pair_cards.append(candidate)

                    if card_names_in_pair[1] == candidate["name"]:
                        pair_cards.append(candidate)
                    else:
                        pair_cards.append(input_card)

                    synergies.append({
                        "cards": pair_cards,
                        "synergy_type": synergy_type,
                        "synergy_score": score,
                        "explanation": explanation
                    })

    # Sort by synergy score DESC
    synergies.sort(key=lambda x: -x["synergy_score"])

    # Limit results
    synergies = synergies[:limit]

    # Meta information
    meta = {
        "input_cards": [{"name": c["name"], "cost": c.get("cost")} for c in input_cards],
        "input_card_categories": input_card_categories,
        "synergies_found": len(synergies),
        "candidates_analyzed": len(filtered_candidates),
        "format": format_type,
        "race": race_slug
    }

    logger.info(
        "find_synergies | %s → %d synergies",
        card_names, len(synergies)
    )

    return {
        "synergies": synergies,
        "meta": meta
    }
