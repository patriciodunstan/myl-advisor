"""Hidden Gems Finder Service - Find underrated cards with high keyword density but low rarity."""
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.card_reader import get_cards_by_race_and_cost, check_banlist
from app.services.alternative_finder import extract_keywords


logger = logging.getLogger(__name__)


# Rarity bonuses (higher bonus = more valuable as hidden gem)
RARITY_BONUS = {
    "comun": 1.5,
    "incomun": 1.3,
    "rara": 1.1,
    "epica": 0.9,
    "legendaria": 0.7,
}


def _get_rarity_bonus(rarity_slug: Optional[str]) -> float:
    """Get rarity bonus for hidden gem calculation."""
    if not rarity_slug:
        return 1.0  # Default bonus if no rarity

    return RARITY_BONUS.get(rarity_slug.lower(), 1.0)


def _generate_reason(
    keyword_count: int,
    rarity_name: Optional[str],
    cost: int,
    gem_score: int,
) -> str:
    """Generate explanation for why a card is a hidden gem."""
    parts = []

    # Keywords part
    parts.append(f"{keyword_count} keywords")

    # Rarity part
    if rarity_name:
        parts.append(f"carta {rarity_name}")

    # Cost part
    parts.append(f"a coste {cost}")

    # Score part
    if gem_score >= 80:
        efficiency_desc = "extremadamente eficiente"
    elif gem_score >= 60:
        efficiency_desc = "muy eficiente"
    elif gem_score >= 40:
        efficiency_desc = "eficiente"
    else:
        efficiency_desc = "moderadamente eficiente"

    return f"{', '.join(parts)} — {efficiency_desc}"


async def find_hidden_gems(
    session: AsyncSession,
    race_slug: str,
    format_type: str = "racial_edicion",
    max_cost: Optional[int] = None,
    min_keywords: int = 2,
    limit: int = 10,
) -> dict:
    """
    Find underrated cards — cards with high keyword density but common/low rarity.

    Process:
    1. Get all cards of given race
    2. For each card, count keywords using extract_keywords
    3. Filter by banlist (exclude banned)
    4. Score each card:
       - keyword_density = keyword_count / max(keyword_count_in_race)
       - rarity_bonus = inversely proportional to rarity
       - cost_efficiency = (keyword_density * rarity_bonus) / (cost + 1)
    5. Sort by gem_score DESC
    6. Return top N with explanations
    """
    logger.info(
        "find_hidden_gems | race=%r format=%r max_cost=%s min_keywords=%d limit=%d",
        race_slug, format_type, max_cost, min_keywords, limit
    )

    # Step 1: Get all cards of the race
    cards = await get_cards_by_race_and_cost(
        session=session,
        race_slug=race_slug,
        max_cost=max_cost,
        exclude_card_name=None,
        limit=200  # Get more cards for analysis
    )

    logger.info("Found %d cards in race %s", len(cards), race_slug)

    if not cards:
        return {
            "hidden_gems": [],
            "meta": {
                "race": race_slug,
                "cards_analyzed": 0,
                "gems_found": 0,
                "format": format_type,
                "error": f"No cards found for race '{race_slug}'"
            }
        }

    # Step 2: Extract keywords from all cards
    card_keywords = {}
    keyword_counts = []

    for card in cards:
        keywords = extract_keywords(card.get("ability"))
        keyword_count = len(keywords)
        card_keywords[card["name"]] = {
            "keywords": keywords,
            "count": keyword_count
        }
        keyword_counts.append(keyword_count)

    # Step 3: Filter by min_keywords
    filtered_cards = [
        card for card in cards
        if card_keywords[card["name"]]["count"] >= min_keywords
    ]

    logger.info(
        "After min_keywords filter (%d): %d cards",
        min_keywords, len(filtered_cards)
    )

    if not filtered_cards:
        return {
            "hidden_gems": [],
            "meta": {
                "race": race_slug,
                "cards_analyzed": len(cards),
                "gems_found": 0,
                "format": format_type,
                "min_keywords": min_keywords,
                "error": f"No cards with at least {min_keywords} keywords found"
            }
        }

    # Step 4: Calculate max keyword count for density normalization
    max_keyword_count = max(
        card_keywords[card["name"]]["count"]
        for card in filtered_cards
    )

    logger.info("Max keyword count in race: %d", max_keyword_count)

    # Step 5: Filter by banlist and score cards
    scored_gems = []

    for card in filtered_cards:
        # Check banlist
        ban_status = await check_banlist(session, card["name"], format_type)
        if ban_status:
            logger.debug("Skipping banned card: %s", card["name"])
            continue

        # Get card data
        card_data = card_keywords[card["name"]]
        keyword_count = card_data["count"]
        keywords_list = list(card_data["keywords"])

        # Calculate keyword density (0-1)
        keyword_density = keyword_count / max_keyword_count if max_keyword_count > 0 else 0

        # Get rarity bonus
        rarity_bonus = _get_rarity_bonus(card.get("rarity_slug"))

        # Calculate cost
        cost = card.get("cost") or 0

        # Calculate cost efficiency (higher = better)
        # Cost + 1 to avoid division by zero
        cost_efficiency = (keyword_density * rarity_bonus) / (cost + 1)

        # Calculate gem score (0-100)
        # Scale cost_efficiency to 0-100 range
        gem_score = int(min(cost_efficiency * 100, 100))

        # Generate reason
        reason = _generate_reason(
            keyword_count=keyword_count,
            rarity_name=card.get("rarity_name"),
            cost=cost,
            gem_score=gem_score
        )

        scored_gems.append({
            "card": card,
            "gem_score": gem_score,
            "keyword_count": keyword_count,
            "keywords": keywords_list,
            "rarity_name": card.get("rarity_name"),
            "cost_efficiency": round(cost_efficiency, 2),
            "reason": reason
        })

    # Step 6: Sort by gem_score DESC, then by cost ASC (cheaper gems first)
    scored_gems.sort(key=lambda x: (-x["gem_score"], x["card"].get("cost", 999)))

    # Limit results
    hidden_gems = scored_gems[:limit]

    # Meta information
    meta = {
        "race": race_slug,
        "cards_analyzed": len(cards),
        "gems_found": len(hidden_gems),
        "format": format_type,
        "min_keywords": min_keywords,
        "max_cost": max_cost,
        "max_keyword_count": max_keyword_count,
        "rarity_bonus_used": RARITY_BONUS
    }

    logger.info(
        "find_hidden_gems | race=%s → %d gems",
        race_slug, len(hidden_gems)
    )

    return {
        "hidden_gems": hidden_gems,
        "meta": meta
    }
