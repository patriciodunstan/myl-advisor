"""Pydantic v2 schemas for request/response models."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


# ---- Request Schemas ----

class AlternativesRequest(BaseModel):
    """Request to find alternative cards."""
    card_name: str = Field(..., min_length=1, description="Name of card to find alternatives for")
    format: str = Field(default="racial_edicion", description="Format (racial_edicion, racial_libre, constructed)")
    max_rarity: Optional[str] = Field(None, description="Maximum rarity to include")
    max_cost: Optional[int] = Field(None, ge=0, description="Maximum cost to consider")


class SynergiesRequest(BaseModel):
    """Request to find synergistic cards."""
    card_names: List[str] = Field(..., min_length=1, max_length=5, description="Names of cards to find synergies for (1-5 cards)")
    format: str = Field(default="racial_edicion", description="Format (racial_edicion, racial_libre, constructed)")
    race_slug: Optional[str] = Field(None, description="Race to filter synergies by")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of synergies to return")


class HiddenGemsRequest(BaseModel):
    """Request to find hidden gems."""
    race_slug: str = Field(..., min_length=1, description="Race to search for hidden gems")
    format: str = Field(default="racial_edicion", description="Format (racial_edicion, racial_libre, constructed)")
    max_cost: Optional[int] = Field(None, ge=0, description="Maximum cost to consider")
    min_keywords: int = Field(default=2, ge=1, description="Minimum keyword count to qualify")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of hidden gems to return")


# ---- Response Schemas ----

class CardInfo(BaseModel):
    """Basic card information."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    cost: Optional[int]
    damage: Optional[int]
    ability: Optional[str]
    keywords: Optional[str]
    edition_title: Optional[str]
    edition_slug: Optional[str]
    race_name: Optional[str]
    race_slug: Optional[str]
    type_name: Optional[str]
    type_slug: Optional[str]
    rarity_name: Optional[str]
    rarity_slug: Optional[str]
    image_path: Optional[str]


class AlternativeCard(BaseModel):
    """An alternative card suggestion."""
    card: CardInfo
    similarity: int = Field(..., ge=0, le=100, description="Similarity score (0-100)")
    reason: str = Field(..., description="Why this is a good alternative")


class AlternativesResponse(BaseModel):
    """Response with alternative cards."""
    alternatives: List[AlternativeCard]
    meta: dict = Field(default_factory=dict, description="Metadata about the analysis")
    llm_analysis: Optional[dict] = Field(None, description="LLM-enhanced strategic analysis (when available)")


class PriceInfo(BaseModel):
    """Price information from a source."""
    source: str
    price_clp: Optional[int]
    price_usd: Optional[float]
    availability: Optional[str]
    url: Optional[str]
    updated_at: Optional[datetime]


class PriceResponse(BaseModel):
    """Response with card prices."""
    card_name: str
    prices: List[PriceInfo]
    avg_price_clp: Optional[int]
    min_price_clp: Optional[int]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    database: str
    zai_configured: bool
    version: str = "0.1.0"


# ---- Synergy Schemas ----

class SynergyPair(BaseModel):
    """A pair of cards that work well together."""
    cards: List[CardInfo]
    synergy_type: str = Field(..., description="Type of synergy: combo, engine, or protection")
    synergy_score: int = Field(..., ge=0, le=100, description="Synergy score (0-100)")
    explanation: str = Field(..., description="Why these cards work well together")


class SynergiesResponse(BaseModel):
    """Response with synergistic card pairs."""
    synergies: List[SynergyPair]
    meta: dict = Field(default_factory=dict, description="Metadata about synergy analysis")


# ---- Hidden Gems Schemas ----

class HiddenGem(BaseModel):
    """An underrated card with high keyword density."""
    card: CardInfo
    gem_score: int = Field(..., ge=0, le=100, description="Gem score (0-100)")
    keyword_count: int = Field(..., ge=0, description="Number of keywords found")
    keywords: List[str] = Field(..., description="List of keywords found")
    rarity_name: Optional[str] = Field(None, description="Rarity name")
    cost_efficiency: float = Field(..., ge=0, description="Cost efficiency score")
    reason: str = Field(..., description="Why this card is a hidden gem")


class HiddenGemsResponse(BaseModel):
    """Response with hidden gem cards."""
    hidden_gems: List[HiddenGem]
    meta: dict = Field(default_factory=dict, description="Metadata about hidden gems analysis")


# ---- Meta Decks Schemas ----

class MetaDeckCardSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    card_name: str
    quantity: int


class MetaDeckInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tor_id: str
    name: str
    author: Optional[str]
    race: Optional[str]
    race_slug: Optional[str]
    format: Optional[str]
    tournament_name: Optional[str]
    tournament_position: Optional[str]
    card_count: int
    scraped_at: datetime
    cards: List[MetaDeckCardSchema] = []


class MetaDeckListResponse(BaseModel):
    decks: List[MetaDeckInfo]
    total: int
    page: int
    pages: int


class MetaDeckDetailResponse(BaseModel):
    deck: MetaDeckInfo


class ScrapeMetaDecksRequest(BaseModel):
    pages: int = Field(default=5, ge=1, le=50)
    start_page: int = Field(default=1, ge=1)


class ScrapeMetaDecksResponse(BaseModel):
    decks_found: int
    decks_saved: int
    errors: int
    message: str


# ---- Internal Schemas ----

class CachedAnalysis(BaseModel):
    """Cached analysis from database."""
    id: int
    request_hash: str
    card_name: str
    analysis_type: str
    response: str
    created_at: datetime
    expires_at: datetime
