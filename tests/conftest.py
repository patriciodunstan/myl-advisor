"""Pytest configuration and fixtures for myl-advisor tests."""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Configure pytest-asyncio
pytest_asyncio.fixture(loop_scope="function")
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.database import Base, get_db, CardAbility, CardPrice, AnalysisCache
from app.shared_models import Base as SharedBase, Card, Edition, Race, Type, Rarity


# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True
)

# Create test session factory
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


@pytest_asyncio.fixture
async def test_session():
    """Create a test database session with all models (shared + advisor)."""
    # Merge shared models into advisor Base for table creation
    for table in SharedBase.metadata.tables.values():
        table.tometadata(Base.metadata)

    # Create all tables from merged Base
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    """Create a test database session (alias for test_session)."""
    # Merge shared models into advisor Base for table creation
    for table in SharedBase.metadata.tables.values():
        table.tometadata(Base.metadata)

    # Create all tables from merged Base
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session):
    """Create a test client with a fake database session."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_card(test_session: AsyncSession):
    """Create a sample Card with related Edition, Race, Type, Rarity in test DB."""
    # Create related entities
    edition = Edition(id=1, slug="core", title="Core Set")
    race = Race(id=1, slug="humanos", name="Humanos")
    type_obj = Type(id=1, slug="aliado", name="Aliado")
    rarity = Rarity(id=1, slug="comun", name="Común")

    test_session.add(edition)
    test_session.add(race)
    test_session.add(type_obj)
    test_session.add(rarity)
    await test_session.flush()

    # Create card
    card = Card(
        id=1,
        edid="DRG001",
        slug="dragon-de-fuego",
        name="Dragon de Fuego",
        edition_id=1,
        race_id=1,
        type_id=1,
        rarity_id=1,
        cost=5,
        damage=3,
        ability="Furia. Al entrar en juego, inflige 2 puntos de daño a todos los aliados enemigos.",
        flavour="Un dragón legendario de las llamas eternas.",
        keywords="Furia, Daño directo",
        image_path="/cards/dragon_fuego.jpg"
    )

    test_session.add(card)
    await test_session.commit()
    await test_session.refresh(card)

    return card


@pytest.fixture
def sample_card_data():
    """Sample card data for tests."""
    return {
        "id": 1,
        "name": "Dragon de Fuego",
        "cost": 5,
        "damage": 3,
        "ability": "Al entrar en juego, inflige 2 puntos de daño a todos los aliados enemigos.",
        "image_path": "/cards/dragon_fuego.jpg",
        "edition_id": 1
    }


@pytest.fixture
def sample_llm_response():
    """Sample LLM response for tests."""
    return """Aquí tienes algunas alternativas a la carta 'Dragon de Fuego':

1. **Bestia de las Sombras** (Costo: 4, Daño: 2)
   - Razón: Tiene una habilidad defensiva que te protege de daño directo
   - Más barata: true

2. **Golem de Tierra** (Costo: 5, Daño: 3)
   - Razón: Tiene resistencia 2, lo que lo hace más difícil de destruir
   - Más barata: false

3. **Espectro Vengativo** (Costo: 3, Daño: 2)
   - Razón: Puede volver del cementerio si es destruido en combate
   - Más barata: true"""
