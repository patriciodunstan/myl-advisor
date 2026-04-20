"""Database connection and new models for MyL Advisor using SQLAlchemy 2.0 async."""
import logging
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import String, Integer, Text, DateTime, Index
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Convert postgresql:// to postgresql+asyncpg:// for async
database_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")

# Async engine and session factory
engine = create_async_engine(
    database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for advisor models."""
    pass


# ---- New Advisor Models ----

class CardAbility(Base):
    """Cache of card abilities extracted from cards table."""
    __tablename__ = "card_abilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    card_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array of extracted keywords
    ability_summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # LLM-generated summary
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index("idx_card_abilities_name", "card_name"),
    )


class CardPrice(Base):
    """Scraped/collected card prices from various sources."""
    __tablename__ = "card_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    card_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    edition_slug: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False, index=True)  # 'mylshop', 'tcgplayer', 'cardmarket', etc
    price_clp: Mapped[float | None] = mapped_column(Integer, nullable=True)  # Price in Chilean Pesos
    price_usd: Mapped[float | None] = mapped_column(Integer, nullable=True)  # Price in USD
    availability: Mapped[str | None] = mapped_column(String, nullable=True)  # 'in_stock', 'out_of_stock', 'preorder'
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index("idx_card_prices_name", "card_name"),
        Index("idx_card_prices_source", "source"),
    )


class AnalysisCache(Base):
    """Cache LLM analysis responses to save API calls."""
    __tablename__ = "analysis_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)  # SHA256 of request
    card_name: Mapped[str] = mapped_column(String, nullable=False)
    analysis_type: Mapped[str] = mapped_column(String, nullable=False, index=True)  # 'alternatives', 'synergy', 'build_advice'
    response: Mapped[str] = mapped_column(Text, nullable=False)  # JSON response
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Indexes
    __table_args__ = (
        Index("idx_analysis_cache_type", "analysis_type"),
        Index("idx_analysis_cache_expires", "expires_at"),
    )


def _is_cache_expired(cache_entry: AnalysisCache) -> bool:
    """Check if cache entry has expired."""
    return cache_entry.expires_at < datetime.utcnow()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    logger.debug("Opening DB connection")
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            logger.debug("DB connection closed")


async def init_db():
    """Initialize database tables for advisor-specific models."""
    logger.info("Creating advisor tables if they don't exist...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Advisor tables created")
    except Exception as e:
        logger.warning("Failed to create advisor tables (non-fatal): %s", e)
        # Non-fatal: app can still serve healthcheck and respond gracefully


async def close_db():
    """Close database connections."""
    logger.info("Closing database connections...")
    await engine.dispose()
    logger.info("Database connections closed")
