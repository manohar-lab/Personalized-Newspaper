import pytest_asyncio
from app.database.session import engine, AsyncSessionLocal

@pytest_asyncio.fixture(autouse=True)
async def cleanup_db_engine():
    yield
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()
