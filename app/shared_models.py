"""SQLAlchemy models for reading from shared MyL database."""
from typing import Optional
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Text, ForeignKey, Index


class Base(DeclarativeBase):
    """Base class for shared models (for querying only)."""
    pass


class Edition(Base):
    """Edition model (read-only)."""
    __tablename__ = "editions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)


class Race(Base):
    """Race model (read-only)."""
    __tablename__ = "races"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)


class Type(Base):
    """Type model (read-only)."""
    __tablename__ = "types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)


class Rarity(Base):
    """Rarity model (read-only)."""
    __tablename__ = "rarities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)


class Card(Base):
    """Card model (read-only)."""
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    edid: Mapped[str | None] = mapped_column(String, nullable=True)
    slug: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    edition_id: Mapped[int] = mapped_column(ForeignKey("editions.id"), nullable=False, index=True)
    race_id: Mapped[int | None] = mapped_column(ForeignKey("races.id"), nullable=True, index=True)
    type_id: Mapped[int | None] = mapped_column(ForeignKey("types.id"), nullable=True, index=True)
    rarity_id: Mapped[int | None] = mapped_column(ForeignKey("rarities.id"), nullable=True, index=True)
    cost: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    damage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ability: Mapped[str | None] = mapped_column(Text, nullable=True)
    flavour: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_path: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships for eager loading
    edition: Mapped["Edition"] = relationship("Edition", lazy="selectin")
    race: Mapped[Optional["Race"]] = relationship("Race", lazy="selectin")
    type: Mapped[Optional["Type"]] = relationship("Type", lazy="selectin")
    rarity: Mapped[Optional["Rarity"]] = relationship("Rarity", lazy="selectin")


class Banlist(Base):
    """Banlist model (read-only)."""
    __tablename__ = "banlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_name: Mapped[str] = mapped_column(String, nullable=False)
    edition: Mapped[str | None] = mapped_column(String, nullable=True)
    format: Mapped[str] = mapped_column(String, nullable=False, index=True)
    restriction: Mapped[str] = mapped_column(String, nullable=False)

    # Indexes
    __table_args__ = (
        Index("idx_banlist_format", "format"),
        Index("idx_banlist_card_format", "card_name", "format", unique=True),
    )
