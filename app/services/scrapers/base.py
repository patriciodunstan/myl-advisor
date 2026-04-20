"""Base scraper class for MyL card price scraping."""
import logging
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)


logger = logging.getLogger(__name__)


@dataclass
class ScrapeResult:
    """Result from a single store scrape."""
    card_name: str
    store_name: str
    price_clp: Optional[int]
    availability: str  # "in_stock", "out_of_stock", "unknown"
    url: Optional[str]
    title: str  # Actual product title from store
    scraped_at: datetime


class BaseScraper(ABC):
    """Base class for store scrapers."""

    def __init__(
        self,
        store_name: str,
        base_url: str,
        max_concurrent: int = 3,
        request_delay: float = 1.0,
        timeout: float = 30.0,
    ):
        self.store_name = store_name
        self.base_url = base_url
        self.max_concurrent = max_concurrent
        self.request_delay = request_delay
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "es-CL,es;q=0.9",
                },
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.NetworkError,
        )),
    )
    async def _fetch(self, url: str) -> Optional[str]:
        """Fetch URL with retry logic and rate limiting."""
        async with self.semaphore:
            await asyncio.sleep(self.request_delay)
            client = await self._get_client()
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    @abstractmethod
    async def search_card(self, card_name: str) -> List[ScrapeResult]:
        """Search for a card in this store. Must be implemented by each store."""
        ...

    def _parse_price_clp(self, price_text: str) -> Optional[int]:
        """Parse price text to integer CLP. Handles '$12.990', '$12990', '12990 CLP'."""
        if not price_text:
            return None
        import re
        # Remove currency symbols and whitespace
        cleaned = re.sub(r'[^\d]', '', price_text)
        if cleaned:
            return int(cleaned)
        return None
