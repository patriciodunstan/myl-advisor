"""Scraper for mesaredondatcg.cl (WooCommerce / WoodMart theme)."""
import logging
from datetime import datetime
from typing import List

from bs4 import BeautifulSoup

from .base import BaseScraper, ScrapeResult

logger = logging.getLogger(__name__)


class MesaRedondaScraper(BaseScraper):
    """Scraper for mesaredondatcg.cl — MYL singles store in Chile."""

    def __init__(self):
        super().__init__(
            store_name="mesaredondatcg",
            base_url="https://mesaredondatcg.cl",
            max_concurrent=2,
            request_delay=2.0,
            timeout=30.0,
        )

    async def search_card(self, card_name: str) -> List[ScrapeResult]:
        """Search mesaredondatcg.cl for a card by name (WooCommerce search)."""
        results = []
        search_url = f"{self.base_url}/?s={card_name}&post_type=product"

        try:
            html = await self._fetch(search_url)
            if not html:
                return results

            soup = BeautifulSoup(html, "html.parser")

            # WoodMart theme uses .wd-product; fallback to generic WooCommerce selectors
            products = (
                soup.select("ul.products li.product")
                or soup.select(".wd-product")
                or soup.select(".type-product")
            )

            for product in products:
                try:
                    # Title — WoodMart uses .wd-entities-title
                    title_elem = (
                        product.select_one(".wd-entities-title")
                        or product.select_one("h2.woocommerce-loop-product__title")
                        or product.select_one("h2")
                    )
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)

                    # URL
                    link_elem = product.select_one("a.wd-entities-title, a[href]")
                    url = link_elem.get("href") if link_elem else None

                    # Price — WoodMart wraps in .tiered-pricing-dynamic-price-wrapper
                    price_elem = (
                        product.select_one(".woocommerce-Price-amount")
                        or product.select_one(".price")
                    )
                    price_text = price_elem.get_text(strip=True) if price_elem else ""
                    price_clp = self._parse_price_clp(price_text)

                    # Stock — WoodMart sets 'instock'/'outofstock' class on product li
                    css_classes = product.get("class", [])
                    if "outofstock" in css_classes:
                        availability = "out_of_stock"
                    elif "instock" in css_classes:
                        availability = "in_stock"
                    else:
                        # Fallback: check .stock element text
                        stock_elem = product.select_one(".stock")
                        if stock_elem:
                            stock_text = stock_elem.get_text(strip=True).lower()
                            availability = "out_of_stock" if "agotado" in stock_text or "out" in stock_text else "in_stock"
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
                    logger.warning("Error parsing product from mesaredondatcg: %s", e)
                    continue

            logger.info("mesaredondatcg.cl: found %d results for '%s'", len(results), card_name)

        except Exception as e:
            logger.error("Error scraping mesaredondatcg.cl for '%s': %s", card_name, e)

        return results
