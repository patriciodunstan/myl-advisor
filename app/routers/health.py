"""Health check endpoint."""
import logging
import asyncio
from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import TimeoutError, DisconnectionError, OperationalError

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
    - Database is accessible (with timeout)
    - Z.ai configuration is present
    """
    logger.info("Health check requested")

    # Check database connectivity with timeout to prevent hanging
    db_status = "connected"
    try:
        # Wait max 5 seconds for database connection
        async with engine.connect() as conn:
            await asyncio.wait_for(conn.execute(text("SELECT 1")), timeout=5.0)
    except asyncio.TimeoutError:
        db_status = "error: database connection timeout"
        logger.error("Database health check timed out after 5 seconds")
    except (TimeoutError, DisconnectionError, OperationalError) as e:
        db_status = f"error: database connection failed: {str(e)}"
        logger.error("Database health check failed: %s", e)
    except Exception as e:
        db_status = f"error: unexpected database error: {str(e)}"
        logger.error("Database health check failed with unexpected error: %s", e)

    # Check Z.ai configuration
    zai_configured = bool(settings.zai_api_key and settings.zai_api_key != "test_key")

    # Determine overall health status
    # Healthy only if DB is connected and Z.ai is configured
    is_healthy = (
        db_status == "connected" and 
        zai_configured
    )

    response = HealthResponse(
        status="healthy" if is_healthy else "unhealthy",
        database=db_status,
        zai_configured=zai_configured,
    )

    logger.info("Health check response: status=%s db=%s zai=%s",
                response.status, response.database, response.zai_configured)

    return response
