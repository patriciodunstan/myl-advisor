"""Scraper for tor.myl.cl — meta decks from tournament results."""
import asyncio
import logging
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://tor.myl.cl"
DECKS_URL = f"{BASE_URL}/decks"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept-Language": "es-CL,es;q=0.9",
}

# Known race slug mappings (display name → slug)
RACE_SLUG_MAP = {
    "dragones": "dragones",
    "dragon": "dragones",
    "elfos": "elfos",
    "elfo": "elfos",
    "humanos": "humanos",
    "humano": "humanos",
    "magos": "magos",
    "mago": "magos",
    "enanos": "enanos",
    "enano": "enanos",
    "desafiantes": "desafiantes",
    "desafiante": "desafiantes",
    "orcos": "orcos",
    "orco": "orcos",
    "muertos": "muertos",
    "muerto": "muertos",
    "ángeles": "angeles",
    "angeles": "angeles",
    "ángel": "angeles",
    "bestias": "bestias",
    "bestia": "bestias",
    "demonios": "demonios",
    "demonio": "demonios",
    "aliados especiales": "aliados_especiales",
}


def _normalize_race_slug(race_text: Optional[str]) -> Optional[str]:
    if not race_text:
        return None
    key = race_text.strip().lower()
    return RACE_SLUG_MAP.get(key, key.replace(" ", "_"))


def _parse_deck_card(row) -> Optional[dict]:
    """Parse a single card row from a deck detail page."""
    cols = row.find_all("td")
    if len(cols) < 2:
        return None
    try:
        quantity_text = cols[0].get_text(strip=True)
        card_name = cols[1].get_text(strip=True)
        if not card_name:
            return None
        quantity = int(quantity_text) if quantity_text.isdigit() else 1
        return {"card_name": card_name, "quantity": quantity}
    except Exception:
        return None


def _parse_deck_list_item(item) -> Optional[dict]:
    """Parse a deck entry from the deck listing page."""
    try:
        # Deck link — extract tor_id from href like /decks/ABC123
        link = item.find("a", href=re.compile(r"/decks/[A-Za-z0-9]+"))
        if not link:
            return None
        href = link.get("href", "")
        tor_id_match = re.search(r"/decks/([A-Za-z0-9]+)", href)
        if not tor_id_match:
            return None
        tor_id = tor_id_match.group(1)

        name = link.get_text(strip=True) or f"Mazo {tor_id}"

        # Author
        author_tag = item.find(class_=re.compile(r"author|jugador|player", re.I))
        author = author_tag.get_text(strip=True) if author_tag else None

        # Race
        race_tag = item.find(class_=re.compile(r"race|raza", re.I))
        race_text = race_tag.get_text(strip=True) if race_tag else None
        race_slug = _normalize_race_slug(race_text)

        # Format
        format_tag = item.find(class_=re.compile(r"format|formato", re.I))
        format_text = format_tag.get_text(strip=True) if format_tag else None

        # Tournament info
        tournament_tag = item.find(class_=re.compile(r"tournament|torneo", re.I))
        tournament_name = tournament_tag.get_text(strip=True) if tournament_tag else None

        position_tag = item.find(class_=re.compile(r"position|posicion|lugar", re.I))
        tournament_position = position_tag.get_text(strip=True) if position_tag else None

        return {
            "tor_id": tor_id,
            "name": name,
            "author": author,
            "race": race_text,
            "race_slug": race_slug,
            "format": format_text,
            "tournament_name": tournament_name,
            "tournament_position": tournament_position,
        }
    except Exception as e:
        logger.debug("Error parsing deck list item: %s", e)
        return None


def _parse_deck_detail(html: str, tor_id: str) -> dict:
    """Parse deck detail page to extract card list."""
    soup = BeautifulSoup(html, "html.parser")
    cards = []

    # Try table rows first
    rows = soup.find_all("tr")
    for row in rows:
        card = _parse_deck_card(row)
        if card:
            cards.append(card)

    # Fallback: look for list items with quantity patterns like "2x Nombre de Carta"
    if not cards:
        for li in soup.find_all("li"):
            text = li.get_text(strip=True)
            match = re.match(r"^(\d+)[xX]?\s+(.+)$", text)
            if match:
                cards.append({
                    "card_name": match.group(2).strip(),
                    "quantity": int(match.group(1)),
                })

    # Extract additional deck metadata from detail page
    meta = {}
    race_tag = soup.find(class_=re.compile(r"race|raza", re.I))
    if race_tag:
        race_text = race_tag.get_text(strip=True)
        meta["race"] = race_text
        meta["race_slug"] = _normalize_race_slug(race_text)

    format_tag = soup.find(class_=re.compile(r"format|formato", re.I))
    if format_tag:
        meta["format"] = format_tag.get_text(strip=True)

    author_tag = soup.find(class_=re.compile(r"author|jugador|player", re.I))
    if author_tag:
        meta["author"] = author_tag.get_text(strip=True)

    tournament_tag = soup.find(class_=re.compile(r"tournament|torneo", re.I))
    if tournament_tag:
        meta["tournament_name"] = tournament_tag.get_text(strip=True)

    position_tag = soup.find(class_=re.compile(r"position|posicion|lugar", re.I))
    if position_tag:
        meta["tournament_position"] = position_tag.get_text(strip=True)

    return {"cards": cards, "meta": meta}


async def fetch_deck_ids_from_page(client: httpx.AsyncClient, page: int) -> list[dict]:
    """Fetch deck stubs from a listing page."""
    url = f"{DECKS_URL}?page={page}"
    try:
        resp = await client.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("Failed to fetch page %d: %s", page, e)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    decks = []

    # Strategy 1: look for links matching /decks/<id>
    links = soup.find_all("a", href=re.compile(r"^/decks/[A-Za-z0-9]{4,10}$"))
    seen_ids = set()
    for link in links:
        href = link.get("href", "")
        m = re.search(r"/decks/([A-Za-z0-9]+)", href)
        if not m:
            continue
        tor_id = m.group(1)
        if tor_id in seen_ids:
            continue
        seen_ids.add(tor_id)

        # Try to get surrounding context (card or list item parent)
        parent = link.find_parent(["li", "div", "tr", "article"])
        if parent:
            parsed = _parse_deck_list_item(parent)
            if parsed:
                decks.append(parsed)
                continue

        # Minimal fallback
        name = link.get_text(strip=True) or f"Mazo {tor_id}"
        decks.append({
            "tor_id": tor_id,
            "name": name,
            "author": None,
            "race": None,
            "race_slug": None,
            "format": None,
            "tournament_name": None,
            "tournament_position": None,
        })

    logger.info("Page %d: found %d deck stubs", page, len(decks))
    return decks


async def fetch_deck_detail(client: httpx.AsyncClient, tor_id: str) -> dict:
    """Fetch and parse a single deck detail page."""
    url = f"{DECKS_URL}/{tor_id}"
    try:
        resp = await client.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return _parse_deck_detail(resp.text, tor_id)
    except httpx.HTTPError as e:
        logger.warning("Failed to fetch deck %s: %s", tor_id, e)
        return {"cards": [], "meta": {}}


async def scrape_meta_decks(
    pages: int = 5,
    start_page: int = 1,
    fetch_cards: bool = True,
    delay_seconds: float = 0.5,
) -> list[dict]:
    """
    Scrape meta decks from tor.myl.cl.

    Returns list of deck dicts ready to be saved to DB:
    {
        tor_id, name, author, race, race_slug, format,
        tournament_name, tournament_position,
        card_count, cards: [{card_name, quantity}]
    }
    """
    results = []

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for page in range(start_page, start_page + pages):
            deck_stubs = await fetch_deck_ids_from_page(client, page)

            if not deck_stubs:
                logger.info("No decks on page %d, stopping early", page)
                break

            for stub in deck_stubs:
                tor_id = stub["tor_id"]
                deck_data = dict(stub)

                if fetch_cards:
                    await asyncio.sleep(delay_seconds)
                    detail = await fetch_deck_detail(client, tor_id)

                    # Override stub metadata with detail page if richer
                    detail_meta = detail.get("meta", {})
                    for field in ("race", "race_slug", "format", "author", "tournament_name", "tournament_position"):
                        if detail_meta.get(field) and not deck_data.get(field):
                            deck_data[field] = detail_meta[field]

                    deck_data["cards"] = detail.get("cards", [])
                else:
                    deck_data["cards"] = []

                deck_data["card_count"] = len(deck_data["cards"])
                results.append(deck_data)
                logger.info("Scraped deck %s (%d cards)", tor_id, deck_data["card_count"])

            # Small delay between pages
            await asyncio.sleep(delay_seconds)

    logger.info("scrape_meta_decks | total=%d decks scraped", len(results))
    return results
