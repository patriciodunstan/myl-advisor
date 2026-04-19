"""Tests for price scrapers."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock, Mock
from datetime import datetime

from app.services.scrapers.base import BaseScraper, ScrapeResult
from app.services.scrapers.cartasmitos import CartasMitosScraper
from app.services.scrapers.huntercard import HunterCardScraper
from app.services.scrapers.lacuevatcg import LaCuevaScraper
from app.services.scrapers.aggregator import search_all_stores, get_cached_prices, save_prices_to_db


def test_parse_price_clp():
    """Test price parsing."""
    scraper = CartasMitosScraper()
    assert scraper._parse_price_clp("$12.990") == 12990
    assert scraper._parse_price_clp("$12990") == 12990
    assert scraper._parse_price_clp("$1.500") == 1500
    assert scraper._parse_price_clp("1.500") == 1500
    assert scraper._parse_price_clp("1500 CLP") == 1500
    assert scraper._parse_price_clp("") is None
    assert scraper._parse_price_clp(None) is None


@pytest.mark.asyncio
async def test_cartasmitos_search_with_mock():
    """Test cartasmitos scraper with mocked HTTP response."""
    mock_html = """
    <ul class="products">
        <li class="product">
            <h2 class="woocommerce-loop-product__title">Genseric - MyL</h2>
            <a href="https://cartasmitos.cl/producto/genseric/">
            <span class="price"><span class="woocommerce-Price-amount">$3.990</span></span>
        </li>
        <li class="product">
            <h2 class="woocommerce-loop-product__title">Genseric Premium Edition</h2>
            <a href="https://cartasmitos.cl/producto/genseric-premium/">
            <span class="price"><span class="woocommerce-Price-amount">$5.990</span></span>
        </li>
    </ul>
    """
    scraper = CartasMitosScraper()
    with patch.object(scraper, '_fetch', new_callable=AsyncMock, return_value=mock_html):
        results = await scraper.search_card("Genseric")

    assert len(results) >= 2
    assert results[0].store_name == "cartasmitos"
    assert results[0].price_clp == 3990
    assert "Genseric" in results[0].title
    assert results[0].url == "https://cartasmitos.cl/producto/genseric/"

    assert results[1].price_clp == 5990
    assert "Premium" in results[1].title

    await scraper.close()


@pytest.mark.asyncio
async def test_cartasmitos_empty_results():
    """Test cartasmitos with no results."""
    scraper = CartasMitosScraper()
    with patch.object(scraper, '_fetch', new_callable=AsyncMock, return_value="<html><body></body></html>"):
        results = await scraper.search_card("NonexistentCard12345")

    assert len(results) == 0
    await scraper.close()


@pytest.mark.asyncio
async def test_huntercard_search_with_mock():
    """Test huntercard scraper with mocked HTTP response."""
    mock_html = """
    <div class="bs-collection__product">
        <h3 class="bs-product__title">Genseric - MyL Deck</h3>
        <a href="https://www.huntercardtcg.com/product/genseric-deck/"></a>
        <div class="bs-product__price">$4.500</div>
    </div>
    """
    scraper = HunterCardScraper()
    with patch.object(scraper, '_fetch', new_callable=AsyncMock, return_value=mock_html):
        results = await scraper.search_card("Genseric")

    assert len(results) >= 1
    assert results[0].store_name == "huntercard"
    assert results[0].price_clp == 4500
    assert "Genseric" in results[0].title

    await scraper.close()


@pytest.mark.asyncio
async def test_lacuevatcg_search_with_mock():
    """Test lacuevatcg scraper with mocked HTTP response."""
    mock_html = """
    <div class="product-item">
        <h3 class="product-title">Genseric MyL Card</h3>
        <a href="/products/genseric-myl"></a>
        <div class="price">$4.200</div>
    </div>
    """
    scraper = LaCuevaScraper()
    with patch.object(scraper, '_fetch', new_callable=AsyncMock, return_value=mock_html):
        results = await scraper.search_card("Genseric")

    assert len(results) >= 1
    assert results[0].store_name == "lacuevatcg"
    assert results[0].price_clp == 4200
    assert "Genseric" in results[0].title
    assert results[0].url is not None
    assert results[0].url.startswith("https://")

    await scraper.close()


@pytest.mark.asyncio
async def test_aggregator_searches_all_stores():
    """Test that aggregator calls all scrapers."""
    with patch('app.services.scrapers.aggregator.get_scrapers') as mock_get:
        scraper1 = AsyncMock()
        scraper1.store_name = "store1"
        scraper1.search_card = AsyncMock(return_value=[
            ScrapeResult("test", "store1", 1000, "in_stock", "http://a", "Card A", datetime.utcnow())
        ])
        scraper2 = AsyncMock()
        scraper2.store_name = "store2"
        scraper2.search_card = AsyncMock(return_value=[])

        mock_get.return_value = [scraper1, scraper2]
        results = await search_all_stores("test")

    assert len(results) == 1
    assert results[0].store_name == "store1"
    assert results[0].price_clp == 1000


@pytest.mark.asyncio
async def test_aggregator_handles_exception():
    """Test that aggregator handles scraper exceptions gracefully."""
    with patch('app.services.scrapers.aggregator.get_scrapers') as mock_get:
        scraper1 = AsyncMock()
        scraper1.store_name = "store1"
        scraper1.search_card = AsyncMock(side_effect=Exception("Network error"))
        scraper2 = AsyncMock()
        scraper2.store_name = "store2"
        scraper2.search_card = AsyncMock(return_value=[
            ScrapeResult("test", "store2", 2000, "in_stock", "http://b", "Card B", datetime.utcnow())
        ])

        mock_get.return_value = [scraper1, scraper2]
        results = await search_all_stores("test")

    assert len(results) == 1
    assert results[0].store_name == "store2"


@pytest.mark.asyncio
async def test_get_cached_prices_empty():
    """Test get_cached_prices when no cache exists."""
    mock_session = AsyncMock()
    mock_scalars_result = Mock()
    mock_scalars_result.all = Mock(return_value=[])
    mock_result = Mock()
    mock_result.scalars = Mock(return_value=mock_scalars_result)
    mock_session.execute = AsyncMock(return_value=mock_result)

    results = await get_cached_prices(mock_session, "TestCard")

    assert len(results) == 0


@pytest.mark.asyncio
async def test_get_cached_prices_with_data():
    """Test get_cached_prices returns cached prices."""
    from app.database import CardPrice
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    mock_price1 = CardPrice(
        id=1,
        card_id=123,
        card_name="TestCard",
        edition_slug=None,
        source="store1",
        price_clp=1000,
        price_usd=None,
        availability="in_stock",
        url="http://a",
        updated_at=now - timedelta(hours=1),
    )
    mock_price2 = CardPrice(
        id=2,
        card_id=123,
        card_name="TestCard",
        edition_slug=None,
        source="store2",
        price_clp=2000,
        price_usd=None,
        availability="out_of_stock",
        url="http://b",
        updated_at=now - timedelta(hours=12),
    )

    mock_session = AsyncMock()
    mock_scalars_result = AsyncMock()
    mock_scalars_result.all = Mock(return_value=[mock_price1, mock_price2])
    mock_result = AsyncMock()
    mock_result.scalars = Mock(return_value=mock_scalars_result)
    mock_session.execute = AsyncMock(return_value=mock_result)

    results = await get_cached_prices(mock_session, "TestCard")

    assert len(results) == 2
    assert results[0].store_name == "store1"
    assert results[0].price_clp == 1000
    assert results[1].store_name == "store2"
    assert results[1].price_clp == 2000


@pytest.mark.asyncio
async def test_save_prices_to_db():
    """Test save_prices_to_db saves prices correctly."""
    from app.database import CardPrice

    results = [
        ScrapeResult("TestCard", "store1", 1000, "in_stock", "http://a", "Card A", datetime.utcnow()),
    ]

    mock_session = AsyncMock()
    mock_session.add = Mock()
    mock_session.flush = AsyncMock()

    with patch('app.services.card_reader.get_card_by_name', new_callable=AsyncMock) as mock_get_card:
        mock_get_card.return_value = {"id": 123}
        await save_prices_to_db(mock_session, results)

    # Verify card was looked up
    mock_get_card.assert_called_once_with(mock_session, "TestCard")

    # Verify price was added to session
    mock_session.add.assert_called_once()
    added_obj = mock_session.add.call_args[0][0]
    assert isinstance(added_obj, CardPrice)
    assert added_obj.card_id == 123
    assert added_obj.source == "store1"
    assert added_obj.price_clp == 1000


@pytest.mark.asyncio
async def test_save_prices_to_db_card_not_found():
    """Test save_prices_to_db skips prices when card not found."""
    results = [
        ScrapeResult("UnknownCard", "store1", 1000, "in_stock", "http://a", "Card A", datetime.utcnow()),
    ]

    mock_session = AsyncMock()
    mock_session.add = Mock()
    mock_session.flush = AsyncMock()

    with patch('app.services.card_reader.get_card_by_name', new_callable=AsyncMock) as mock_get_card:
        mock_get_card.return_value = None  # Card not found
        await save_prices_to_db(mock_session, results)

    # Verify price was NOT added to session
    mock_session.add.assert_not_called()
