"""Scraper for api.myl.cl/cards/decks — meta decks from tor.myl.cl."""
import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://api.myl.cl"
DECKS_ENDPOINT = f"{API_BASE}/cards/decks"

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
    """Parse a single deck entry from the API response."""
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
        # Count duplicates for quantity
        card_counts: dict[int, int] = {}
        for cid in card_ids:
            card_counts[cid] = card_counts.get(cid, 0) + 1

        return {
            "slug": slug,
            "title": raw.get("title") or f"Mazo {slug}",
            "description": raw.get("description") or "",
            "author": author,
            "owner_id": owner.get("id"),
            "owner_ranking": owner.get("ranking"),
            "views": int(raw.get("views") or 0),
            "is_public": bool(raw.get("is_public")),
            "card_counts": card_counts,  # {card_id: quantity}
            "card_ids": list(card_counts.keys()),  # unique IDs
        }
    except Exception as e:
        logger.debug("Error parsing deck: %s", e)
        return None


async def fetch_decks_page(
    client: httpx.AsyncClient,
    page: int,
    limit: int = 30,
) -> tuple[list[dict], int]:
    """
    Fetch one page of decks from api.myl.cl.

    Returns (decks, total_pages).
    """
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
    delay_seconds: float = 0.3,
) -> list[dict]:
    """
    Scrape meta decks from api.myl.cl.

    Returns list of raw deck dicts with card_counts ({card_id: quantity}).
    Card ID → name resolution happens in the service layer using the local DB.
    """
    results = []

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for page_num in range(start_page, start_page + pages):
            decks, total_pages = await fetch_decks_page(client, page_num)

            if not decks:
                logger.info("No decks on page %d, stopping", page_num)
                break

            results.extend(decks)
            logger.info("Scraped page %d/%d — %d total decks so far", page_num, total_pages, len(results))

            if page_num >= total_pages:
                logger.info("Reached last page (%d)", total_pages)
                break

            await asyncio.sleep(delay_seconds)

    logger.info("scrape_meta_decks done | total=%d", len(results))
    return results
