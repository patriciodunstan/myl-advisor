"""Scraper for lacuevatcg.cl (Shopify store)."""
import logging
import re
import json
from typing import List, Optional
from datetime import datetime
from bs4 import BeautifulSoup

from .base import BaseScraper, ScrapeResult

logger = logging.getLogger(__name__)


class LaCuevaScraper(BaseScraper):
    """Scraper for lacuevatcg.cl — Shopify store."""

    def __init__(self):
        super().__init__(
            store_name="lacuevatcg",
            base_url="https://lacuevatcg.cl",
            max_concurrent=3,
            request_delay=1.0,
            timeout=30.0,
        )

    async def search_card(self, card_name: str) -> List[ScrapeResult]:
        """Search lacuevatcg.cl for a card by name."""
        results = []
        # Shopify search URL
        search_url = f"{self.base_url}/search?q={card_name}"

        try:
            html = await self._fetch(search_url)
            if not html:
                return results

            # Try to extract embedded JSON first (Shopify often includes search results in script tags)
            json_results = self._try_parse_shopify_json(html, card_name)
            if json_results:
                results.extend(json_results)
                logger.info("lacuevatcg.cl (JSON): found %d results for '%s'", len(json_results), card_name)
                return results

            # Fallback to HTML parsing
            soup = BeautifulSoup(html, "html.parser")

            # Shopify product list items
            products = (
                soup.select(".product-item")
                or soup.select(".product-card")
                or soup.select(".grid-product")
                or soup.select("li.product")
            )

            for product in products:
                try:
                    # Title
                    title_elem = (
                        product.select_one(".product-title")
                        or product.select_one(".product-card__title")
                        or product.select_one("h3")
                        or product.select_one("a.product-item__title")
                    )
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)

                    # Link
                    link_elem = product.select_one("a[href]")
                    url = link_elem.get("href", "") if link_elem else None
                    if url and not url.startswith("http"):
                        url = self.base_url + url

                    # Price
                    price_elem = (
                        product.select_one(".price")
                        or product.select_one(".price-item")
                        or product.select_one(".product-card__price")
                        or product.select_one(".product__price")
                    )
                    price_text = price_elem.get_text(strip=True) if price_elem else ""
                    price_clp = self._parse_price_clp(price_text)

                    # Availability
                    stock_elem = product.select_one(".badge--soldout") or product.select_one(".sold-out")
                    availability = "out_of_stock" if stock_elem else "unknown"

                    results.append(ScrapeResult(
                        card_name=card_name,
                        store_name=self.store_name,
                        price_clp=price_clp,
                        availability=availability,
                        url=url,
                        title=title,
                        scraped_at=datetime.utcnow(),
                    ))

                except Exception as e:
                    logger.warning("Error parsing product from lacuevatcg: %s", e)
                    continue

            logger.info("lacuevatcg.cl (HTML): found %d results for '%s'", len(results), card_name)

        except Exception as e:
            logger.error("Error scraping lacuevatcg.cl for '%s': %s", card_name, e)

        return results

    def _try_parse_shopify_json(self, html: str, card_name: str) -> Optional[List[ScrapeResult]]:
        """Try to extract search results from embedded Shopify JSON."""
        try:
            # Shopify often includes search results in script tags with "searchResult" or "products"
            # Look for patterns like: {"searchResult":{"items":[...]}}
            pattern = r'searchResult["\s]*:\s*({[^}]*items[^}]*})'
            match = re.search(pattern, html)
            if not match:
                return None

            json_str = match.group(1)
            data = json.loads(json_str)

            if not data or "items" not in data:
                return None

            results = []
            for item in data["items"]:
                try:
                    title = item.get("title", "")
                    url = item.get("url", "")
                    if url and not url.startswith("http"):
                        url = self.base_url + url

                    # Shopify JSON often has "price" in cents or formatted
                    price_str = item.get("price", item.get("price_value", ""))
                    price_clp = None
                    if price_str:
                        # Try to parse as integer (could be in cents)
                        try:
                            price_clp = int(float(str(price_str).replace(",", "")))
                        except (ValueError, TypeError):
                            price_clp = self._parse_price_clp(str(price_str))

                    availability = "unknown"
                    if item.get("available") is False:
                        availability = "out_of_stock"
                    elif item.get("available") is True:
                        availability = "in_stock"

                    results.append(ScrapeResult(
                        card_name=card_name,
                        store_name=self.store_name,
                        price_clp=price_clp,
                        availability=availability,
                        url=url,
                        title=title,
                        scraped_at=datetime.utcnow(),
                    ))
                except Exception as e:
                    logger.warning("Error parsing JSON item from lacuevatcg: %s", e)
                    continue

            return results if results else None

        except Exception as e:
            logger.debug("Failed to parse Shopify JSON from lacuevatcg: %s", e)
            return None
