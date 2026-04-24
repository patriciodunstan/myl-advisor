"""Scraper for api.myl.cl/cards/decks — meta decks from tor.myl.cl."""
import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://api.myl.cl"
DECKS_ENDPOINT = f"{API_BASE}/cards/decks"
DECK_DETAIL_ENDPOINT = f"{API_BASE}/cards/deck"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://tor.myl.cl",
    "Referer": "https://tor.myl.cl/",
}


def _parse_card_ids(cards_str: Optional[str]) -> list[int]:
    """Parse comma-separated card ID string into list of ints."""
    if not cards_str:
        return []
    ids = []
    for part in cards_str.split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return ids


def _parse_deck(raw: dict) -> Optional[dict]:
    """Parse a single deck entry from the listing API."""
    try:
        slug = raw.get("slug", "").strip()
        if not slug:
            return None

        owner = raw.get("owner") or {}
        nickname = owner.get("nickname") or ""
        name = owner.get("name") or ""
        lastname = owner.get("lastname") or ""
        author = nickname or f"{name} {lastname}".strip() or None

        card_ids = _parse_card_ids(raw.get("cards"))
        card_counts: dict[int, int] = {}
        for cid in card_ids:
            card_counts[cid] = card_counts.get(cid, 0) + 1

        return {
            "slug": slug,
            "title": raw.get("title") or f"Mazo {slug}",
            "author": author,
            "is_public": bool(raw.get("is_public")),
            "card_counts": card_counts,
            "resolved_cards": None,  # populated by fetch_deck_detail if public
        }
    except Exception as e:
        logger.debug("Error parsing deck: %s", e)
        return None


async def fetch_deck_detail(
    client: httpx.AsyncClient,
    slug: str,
) -> Optional[list[dict]]:
    """
    Fetch resolved card names from /cards/deck/{slug}.
    Returns list of {card_name, quantity} or None if private/error.
    """
    url = f"{DECK_DETAIL_ENDPOINT}/{slug}"
    try:
        resp = await client.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("status") != "OK":
            return None

        cards_data = data.get("cards") or {}
        # cards_data can be a dict {card_id: card_obj} or list
        result = []
        if isinstance(cards_data, dict):
            for card_obj in cards_data.values():
                name = card_obj.get("name")
                qty = int(card_obj.get("quantity") or card_obj.get("qty") or 1)
                if name:
                    result.append({"card_name": name, "quantity": qty})
        elif isinstance(cards_data, list):
            for card_obj in cards_data:
                name = card_obj.get("name")
                qty = int(card_obj.get("quantity") or card_obj.get("qty") or 1)
                if name:
                    result.append({"card_name": name, "quantity": qty})

        return result if result else None
    except Exception as e:
        logger.debug("fetch_deck_detail failed for %s: %s", slug, e)
        return None


async def fetch_decks_page(
    client: httpx.AsyncClient,
    page: int,
    limit: int = 30,
) -> tuple[list[dict], int]:
    """Fetch one page of decks from api.myl.cl. Returns (decks, total_pages)."""
    url = f"{DECKS_ENDPOINT}/{limit}/{page}"
    try:
        resp = await client.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("Failed to fetch decks page %d: %s", page, e)
        return [], 0

    if data.get("status") != "OK":
        logger.warning("API returned non-OK status on page %d: %s", page, data.get("status"))
        return [], 0

    raw_decks = data.get("decks") or []
    total_pages = int(data.get("total_pages") or 0)

    parsed = []
    for raw in raw_decks:
        deck = _parse_deck(raw)
        if deck:
            parsed.append(deck)

    logger.info("Page %d: %d decks parsed (total_pages=%d)", page, len(parsed), total_pages)
    return parsed, total_pages


async def scrape_meta_decks(
    pages: int = 5,
    start_page: int = 1,
    delay_seconds: float = 0.4,
) -> list[dict]:
    """
    Scrape meta decks from api.myl.cl.

    For public decks, fetches full card names from /cards/deck/{slug}.
    For private decks, returns card_counts dict (IDs only, resolved by service via DB).
    """
    results = []

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for page_num in range(start_page, start_page + pages):
            decks, total_pages = await fetch_decks_page(client, page_num)

            if not decks:
                logger.info("No decks on page %d, stopping", page_num)
                break

            for deck in decks:
                if deck["is_public"]:
                    await asyncio.sleep(0.2)
                    resolved = await fetch_deck_detail(client, deck["slug"])
                    if resolved:
                        deck["resolved_cards"] = resolved
                        logger.debug("Resolved %d cards for public deck %s", len(resolved), deck["slug"])

            results.extend(d for d in decks if d["is_public"])
            logger.info("Page %d/%d — %d total decks", page_num, total_pages, len(results))

            if page_num >= total_pages:
                break

            await asyncio.sleep(delay_seconds)

    logger.info("scrape_meta_decks done | total=%d", len(results))
    return results
