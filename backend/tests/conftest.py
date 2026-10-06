import os
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.models.base import Base
import app.models
import app.learning.models
from app.database import session as db_session_module
from app.database.seed_topics import seed_topics
from app.database.seed_feeds import seed_sources_and_feeds
from app.database.seed_articles import seed_articles
from app.main import app

# Create a shared test engine
test_engine = create_async_engine(
    "sqlite+aiosqlite:///test_newspaper.db",
    echo=False,
    future=True,
)
TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Monkey-patch db_session_module so all services use test_engine if needed
db_session_module.engine = test_engine
db_session_module.AsyncSessionLocal = TestAsyncSessionLocal

@pytest_asyncio.fixture(scope="session", autouse=True)
async def init_test_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestAsyncSessionLocal() as session:
        await seed_topics(session)
        await seed_sources_and_feeds(session)
        await seed_articles(session)
    
    yield
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()
    if os.path.exists("test_newspaper.db"):
        try:
            os.remove("test_newspaper.db")
        except Exception:
            pass

@pytest_asyncio.fixture(autouse=True)
async def cleanup_db_engine():
    yield

@pytest_asyncio.fixture
async def db_session():
    async with TestAsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()

