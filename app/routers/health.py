"""Health check endpoint."""
import logging
from fastapi import APIRouter
from sqlalchemy import text

from app.database import engine
from app.schemas import HealthResponse
from app.config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """
    Health check endpoint.

    Verifies:
    - API is running
    - Database is accessible
    - Z.ai configuration is present
    """
    logger.info("Health check requested")

    # Check database connectivity
    db_status = "connected"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"
        logger.error("Database health check failed: %s", e)

    # Check Z.ai configuration
    zai_configured = bool(settings.zai_api_key and settings.zai_api_key != "test_key")

    response = HealthResponse(
        status="healthy",
        database=db_status,
        zai_configured=zai_configured,
    )

    logger.info("Health check response: status=%s db=%s zai=%s",
                response.status, response.database, response.zai_configured)

    return response
