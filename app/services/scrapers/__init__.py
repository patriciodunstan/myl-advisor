"""Package for MyL card price scrapers."""
from .base import BaseScraper, ScrapeResult
from .cartasmitos import CartasMitosScraper
from .huntercard import HunterCardScraper
from .lacuevatcg import LaCuevaScraper

__all__ = [
    "BaseScraper",
    "ScrapeResult",
    "CartasMitosScraper",
    "HunterCardScraper",
    "LaCuevaScraper",
]
