"""Tests for LLM client functions."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import (
    _hash_request,
    get_cached_analysis,
    cache_analysis,
    analyze_alternatives_with_llm,
)
from app.database import AnalysisCache


def test_hash_request():
    """Test cache key generation."""
    request_data = {"query": "Test query for cache", "card": "Dragon"}

    key1 = _hash_request(request_data)
    key2 = _hash_request(request_data)

    # Same query should generate same hash
    assert key1 == key2
    assert len(key1) == 64  # SHA-256 hash length

    # Different query should generate different hash
    key3 = _hash_request({"query": "Different query", "card": "Dragon"})
    assert key1 != key3


@pytest.mark.asyncio
async def test_get_cached_analysis_miss(test_session: AsyncSession):
    """Test cache miss scenario (fresh query)."""
    request_hash = "nonexistent_hash"

    # Cache should return None for new query
    cached = await get_cached_analysis(test_session, request_hash)

    assert cached is None


@pytest.mark.asyncio
async def test_cache_and_retrieve_analysis(test_session: AsyncSession):
    """Test saving and retrieving cached analysis."""
    request_hash = "test_hash_12345"
    card_name = "Dragon de Fuego"
    analysis_type = "alternatives"
    response = {
        "llm_summary": "Test response",
        "enhanced_reasoning": True
    }

    # Save to cache
    await cache_analysis(
        test_session,
        request_hash,
        card_name,
        analysis_type,
        response,
        ttl_hours=24
    )

    # Retrieve from cache
    cached = await get_cached_analysis(test_session, request_hash)

    assert cached is not None
    assert cached["response"] == response
    assert "created_at" in cached
    assert "expires_at" in cached


@pytest.mark.asyncio
async def test_analyze_alternatives_with_cache_hit(test_session: AsyncSession):
    """Test analyze with cached response."""
    request_hash = "test_hash_cached"
    card_name = "Dragon de Fuego"
    target_card = {"name": card_name, "cost": 5}
    alternatives = []
    request_data = {"target": target_card, "alternatives": alternatives}
    cached_response = {"llm_summary": "Cached summary", "enhanced_reasoning": True}

    # Pre-populate cache
    await cache_analysis(
        test_session,
        request_hash,
        card_name,
        "alternatives",
        cached_response,
        ttl_hours=24
    )

    # Mock hash to return our test hash
    with patch('app.llm.client._hash_request', return_value=request_hash):
        # Mock config to not have API key (so we only use cache)
        with patch('app.llm.client.settings') as mock_settings:
            mock_settings.zai_api_key = "test_key"

            result = await analyze_alternatives_with_llm(
                test_session,
                target_card,
                alternatives,
                request_data
            )

    assert result == cached_response


@pytest.mark.asyncio
async def test_analyze_alternatives_no_api_key(test_session: AsyncSession):
    """Test analyze with no API key configured."""
    target_card = {"name": "Dragon", "cost": 5}
    alternatives = []
    request_data = {"target": target_card, "alternatives": alternatives}

    # Mock hash to return unique hash
    with patch('app.llm.client._hash_request', return_value="new_hash_123"):
        # Mock config to not have API key
        with patch('app.llm.client.settings') as mock_settings:
            mock_settings.zai_api_key = "test_key"

            result = await analyze_alternatives_with_llm(
                test_session,
                target_card,
                alternatives,
                request_data
            )

    # Should return None (use keyword-only results)
    assert result is None


@pytest.mark.asyncio
async def test_analyze_alternatives_with_llm_call(test_session: AsyncSession, sample_llm_response):
    """Test analyze with actual LLM call (mocked)."""
    request_hash = "new_llm_hash"
    target_card = {"name": "Dragon de Fuego", "cost": 5, "race_name": "Humanos", "type_name": "Aliado"}
    alternatives = [
        {"card": {"name": "Golem", "cost": 5, "damage": 3}, "similarity": 80, "reason": "Similar stats"}
    ]
    request_data = {"target": target_card, "alternatives": alternatives}

    # Mock hash
    with patch('app.llm.client._hash_request', return_value=request_hash):
        # Mock config to have valid API key
        with patch('app.llm.client.settings') as mock_settings:
            mock_settings.zai_api_key = "valid_key"
            mock_settings.zai_model = "glm-4.7-flash"
            mock_settings.cache_ttl_hours = 24

            # Mock OpenAI client's chat.completions.create method
            with patch('app.llm.client.client.chat.completions.create', new_callable=AsyncMock) as mock_create:
                # Mock response
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = sample_llm_response
                mock_create.return_value = mock_response

                result = await analyze_alternatives_with_llm(
                    test_session,
                    target_card,
                    alternatives,
                    request_data
                )

    assert result is not None
    assert "llm_summary" in result
    assert result["llm_summary"] == sample_llm_response
    assert result["enhanced_reasoning"] is True

    # Verify LLM was called
    mock_create.assert_called_once()
