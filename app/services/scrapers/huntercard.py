"""Scraper for huntercardtcg.com (WooCommerce store)."""
import logging
from typing import List
from datetime import datetime
from bs4 import BeautifulSoup

from .base import BaseScraper, ScrapeResult

logger = logging.getLogger(__name__)


class HunterCardScraper(BaseScraper):
    """Scraper for huntercardtcg.com — WooCommerce store (slower server)."""

    def __init__(self):
        super().__init__(
            store_name="huntercard",
            base_url="https://www.huntercardtcg.com",
            max_concurrent=2,
            request_delay=3.0,  # Server is slow
            timeout=30.0,
        )

    async def search_card(self, card_name: str) -> List[ScrapeResult]:
        """Search huntercardtcg.com for a card by name."""
        results = []
        # WooCommerce search URL
        search_url = f"{self.base_url}/?s={card_name}&post_type=product"

        try:
            html = await self._fetch(search_url)
            if not html:
                return results

            soup = BeautifulSoup(html, "html.parser")

            # Custom WordPress theme selectors
            products = (
                soup.select(".bs-collection__product")
                or soup.select(".product")
                or soup.select("ul.products li.product")
            )

            for product in products:
                try:
                    # Title
                    title_elem = (
                        product.select_one(".bs-product__title")
                        or product.select_one("h2.woocommerce-loop-product__title")
                        or product.select_one("h2")
                        or product.select_one(".product-title")
                    )
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)

                    # Link
                    link_elem = product.select_one("a")
                    url = link_elem.get("href", "") if link_elem else None

                    # Price
                    price_elem = (
                        product.select_one(".bs-product__price")
                        or product.select_one(".price")
                        or product.select_one(".woocommerce-Price-amount")
                    )
                    price_text = price_elem.get_text(strip=True) if price_elem else ""
                    price_clp = self._parse_price_clp(price_text)

                    # Availability (HunterCard doesn't show stock clearly)
                    availability = "unknown"

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
                    logger.warning("Error parsing product from huntercard: %s", e)
                    continue

            logger.info("huntercardtcg.com: found %d results for '%s'", len(results), card_name)

        except Exception as e:
            logger.error("Error scraping huntercardtcg.com for '%s': %s", card_name, e)

        return results
