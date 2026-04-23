"""FastAPI app factory for myl-advisor."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db, close_db
from app.routers import health, alternatives, prices, synergies, hidden_gems, cards

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    logger.info("Starting MyL Advisor...")
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning("Database initialization failed (non-fatal): %s", e)

    yield

    logger.info("Shutting down MyL Advisor...")
    await close_db()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        description="AI-powered advisor for Mitos y Leyendas card game",
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health.router)
    app.include_router(alternatives.router)
    app.include_router(prices.router)
    app.include_router(synergies.router)
    app.include_router(hidden_gems.router)
    app.include_router(cards.router)

    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "service": settings.app_name,
            "version": "0.1.0",
            "status": "running",
            "endpoints": {
                "health": "/health",
                "alternatives": "/api/advisor/alternatives",
                "synergies": "/api/advisor/synergies",
                "hidden_gems": "/api/advisor/hidden-gems",
                "prices": "/api/advisor/prices/{card_name}",
                "docs": "/docs" if settings.debug else None,
            }
        }

    logger.info(f"{settings.app_name} initialized")
    return app


app = create_app()
