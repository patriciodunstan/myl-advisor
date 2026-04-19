"""Tests for health check endpoint."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check endpoint."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert "database" in data
    assert "zai_configured" in data
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test root endpoint."""
    response = await client.get("/")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "running"
    assert "service" in data
    assert data["version"] == "0.1.0"
    assert "endpoints" in data
