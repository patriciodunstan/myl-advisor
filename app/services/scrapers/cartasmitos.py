"""Scraper for cartasmitos.cl (WooCommerce store)."""
import logging
from typing import List, Optional
from bs4 import BeautifulSoup

from .base import BaseScraper, ScrapeResult

logger = logging.getLogger(__name__)


class CartasMitosScraper(BaseScraper):
    """Scraper for cartasmitos.cl — largest MyL card store in Chile."""

    def __init__(self):
        super().__init__(
            store_name="cartasmitos",
            base_url="https://cartasmitos.cl",
            max_concurrent=2,
            request_delay=2.0,  # Be gentle, they get 508 errors
            timeout=30.0,
        )

    async def search_card(self, card_name: str) -> List[ScrapeResult]:
        """Search cartasmitos.cl for a card by name."""
        from datetime import datetime

        results = []
        # WooCommerce search URL
        search_url = f"{self.base_url}/?s={card_name}&post_type=product"

        try:
            html = await self._fetch(search_url)
            if not html:
                return results

            soup = BeautifulSoup(html, "html.parser")

            # WooCommerce product list items — try multiple selectors
            products = (
                soup.select("ul.products li.product")
                or soup.select("div.product")
                or soup.select(".type-product")
            )

            for product in products:
                try:
                    # Title
                    title_elem = (
                        product.select_one("h2.woocommerce-loop-product__title")
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
                    price_elem = product.select_one(".price") or product.select_one(".woocommerce-Price-amount")
                    price_text = price_elem.get_text(strip=True) if price_elem else ""
                    price_clp = self._parse_price_clp(price_text)

                    # Availability
                    stock_elem = product.select_one(".stock") or product.select_one(".out-of-stock")
                    if stock_elem:
                        availability = "out_of_stock" if "agotado" in stock_elem.get_text(strip=True).lower() or "out" in stock_elem.get_text(strip=True).lower() else "in_stock"
                    else:
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
                    logger.warning("Error parsing product from cartasmitos: %s", e)
                    continue

            logger.info("cartasmitos.cl: found %d results for '%s'", len(results), card_name)

        except Exception as e:
            logger.error("Error scraping cartasmitos.cl for '%s': %s", card_name, e)

        return results
