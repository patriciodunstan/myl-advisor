"""Alternative Finder Service - Find cheaper alternatives based on keywords."""
import logging
from typing import List, Optional, Set

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ability_parser import parse_ability, calculate_effect_similarity
from app.services.card_reader import get_card_by_name, get_cards_by_race_and_cost, check_banlist
from app.services.keyword_extractor import extract_keywords as _extract_keywords


# Re-export for backward compatibility
extract_keywords = _extract_keywords


logger = logging.getLogger(__name__)


def calculate_similarity(target_keywords: Set[str], candidate_keywords: Set[str]) -> int:
    """Calculate similarity score based on shared keywords."""
    if not target_keywords:
        # If target has no keywords, assume 0 similarity
        return 0

    if not candidate_keywords:
        # If candidate has no keywords, but target does, low similarity
        return 10

    shared = target_keywords & candidate_keywords
    total_unique = target_keywords | candidate_keywords

    if not total_unique:
        return 0

    # Similarity = (shared / total_unique) * 100
    similarity = (len(shared) / len(total_unique)) * 100
    return int(similarity)


async def find_alternatives(
    session: AsyncSession,
    card_name: str,
    format_type: str = "racial_edicion",
    max_rarity: Optional[str] = None,
    max_cost: Optional[int] = None,
    limit: int = 10,
) -> dict:
    """
    Find alternative cards based on keyword similarity.

    Process:
    1. Find target card in DB
    2. Get its race, type, cost, ability text
    3. Query cards of SAME race with cost <= max_cost (or target cost + 1)
    4. Filter by banlist (exclude banned cards)
    5. Use keyword overlap on ability text to score similarity
    6. Rank by: similarity DESC, then cost ASC (cheaper first)
    7. Return top N alternatives with reasons
    """
    logger.info(
        "find_alternatives | card_name=%r format=%r max_rarity=%s max_cost=%s limit=%d",
        card_name, format_type, max_rarity, max_cost, limit
    )

    # Step 1: Get target card
    target_card = await get_card_by_name(session, card_name)
    if not target_card:
        logger.warning("find_alternatives | target card not found: %r", card_name)
        return {
            "alternatives": [],
            "meta": {
                "target_card_found": False,
                "error": f"Card '{card_name}' not found in database"
            }
        }

    # Extract target keywords and ability profile
    target_keywords = extract_keywords(target_card.get("ability"))
    target_profile = parse_ability(target_card.get("ability"))
    logger.debug("Target keywords: %s", target_keywords)
    logger.debug("Target profile: %s", target_profile)

    # Determine max cost for alternatives
    target_cost = target_card.get("cost")
    if max_cost is None and target_cost is not None:
        search_max_cost = target_cost + 1  # Allow slightly more expensive
    elif max_cost is not None:
        search_max_cost = max_cost
    else:
        search_max_cost = None

    # Get race for filtering
    race_slug = target_card.get("race_slug")
    if not race_slug:
        logger.warning("find_alternatives | target card has no race: %r", card_name)
        return {
            "alternatives": [],
            "meta": {
                "target_card_found": True,
                "error": "Target card has no race defined"
            }
        }

    # Step 2: Get candidate cards of same race
    candidates = await get_cards_by_race_and_cost(
        session=session,
        race_slug=race_slug,
        max_cost=search_max_cost,
        exclude_card_name=card_name,
        limit=50  # Get more candidates, we'll filter and rank
    )

    logger.info("Found %d candidate cards", len(candidates))

    # Step 3: Filter candidates and score them
    scored_alternatives = []

    for candidate in candidates:
        # Filter by rarity if specified
        if max_rarity:
            candidate_rarity = candidate.get("rarity_slug") or candidate.get("rarity_name", "")
            # Simple rarity comparison (can be enhanced)
            rarity_order = {"comun": 1, "incomun": 2, "rara": 3, "epica": 4, "legendaria": 5}
            max_rarity_level = rarity_order.get(max_rarity.lower(), 99)
            candidate_level = rarity_order.get(candidate_rarity.lower(), 99)
            if candidate_level > max_rarity_level:
                continue

        # Check banlist
        ban_status = await check_banlist(session, candidate["name"], format_type)
        if ban_status:
            logger.debug("Skipping banned card: %s (%s)", candidate["name"], ban_status.get("restriction"))
            continue

        # Score similarity
        candidate_keywords = extract_keywords(candidate.get("ability"))
        candidate_profile = parse_ability(candidate.get("ability"))

        # Calculate both similarities
        keyword_sim = calculate_similarity(target_keywords, candidate_keywords)
        effect_sim = calculate_effect_similarity(target_profile, candidate_profile)

        # Combined score (70% keyword + 30% effect similarity)
        combined_similarity = int(keyword_sim * 0.7 + effect_sim * 100 * 0.3)

        # Only include cards with at least some similarity (20% threshold)
        if combined_similarity >= 20:
            scored_alternatives.append({
                "card": candidate,
                "similarity": combined_similarity,
                "keyword_similarity": keyword_sim,
                "effect_similarity": effect_sim,
                "candidate_keywords": candidate_keywords,
            })

    # Step 4: Sort by similarity DESC, then cost ASC
    scored_alternatives.sort(key=lambda x: (-x["similarity"], x["card"].get("cost", 999)))

    # Step 5: Generate reasons and format results
    alternatives = []
    for alt in scored_alternatives[:limit]:
        candidate = alt["card"]
        similarity = alt["similarity"]
        shared = target_keywords & alt["candidate_keywords"]

        # Generate reason
        if shared:
            reason = f"Comparte {len(shared)} habilidad(es): {', '.join(sorted(shared))}"
        else:
            reason = "Similar en coste y tipo, sin habilidades compartidas"

        # Add cost difference
        if target_cost is not None and candidate.get("cost") is not None:
            cost_diff = candidate["cost"] - target_cost
            if cost_diff < 0:
                reason += f". {abs(cost_diff)} de oro más barata"
            elif cost_diff > 0:
                reason += f". {cost_diff} de oro más cara"

        alternatives.append({
            "card": candidate,
            "similarity": similarity,
            "reason": reason,
        })

    # Meta information
    meta = {
        "target_card_found": True,
        "target_card": {
            "name": target_card["name"],
            "cost": target_card["cost"],
            "race": target_card["race_name"],
            "type": target_card["type_name"],
            "rarity": target_card["rarity_name"],
            "keywords": list(target_keywords),
        },
        "candidates_found": len(candidates),
        "alternatives_found": len(scored_alternatives),
        "alternatives_returned": len(alternatives),
        "format": format_type,
    }

    logger.info(
        "find_alternatives | %s → %d alternatives",
        card_name, len(alternatives)
    )

    return {
        "alternatives": alternatives,
        "meta": meta
    }
