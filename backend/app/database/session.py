import socket
from typing import AsyncGenerator, Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import settings
from app.core.logging import logger

# Async Engine configuration
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing asynchronous database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_database_connection() -> Dict[str, Any]:
    """
    Performs database connection test by executing a simple query.
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {
            "status": "connected",
            "database": "postgresql" if "postgresql" in settings.DATABASE_URL else "sqlite",
            "detail": "Successfully connected to database instance.",
        }
    except Exception as exc:
        logger.warning(f"Database health check failed: {str(exc)}")
        return {
            "status": "disconnected",
            "database": "postgresql",
            "detail": f"Connection failed: {str(exc)}",
        }
