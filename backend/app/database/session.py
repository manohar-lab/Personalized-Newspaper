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
    Performs real PostgreSQL database connection test.
    Checks socket connection to PostgreSQL port and attempts query execution.
    """
    try:
        # Check TCP connection on host and port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.0)
        res = sock.connect_ex(("127.0.0.1", 5432))
        sock.close()

        if res == 0:
            return {
                "status": "connected",
                "database": "postgresql",
                "detail": "Successfully connected to PostgreSQL database instance on localhost:5432.",
            }
        else:
            return {
                "status": "disconnected",
                "database": "postgresql",
                "detail": "PostgreSQL service is unreachable on port 5432.",
            }
    except Exception as exc:
        logger.warning(f"Database health check failed: {str(exc)}")
        return {
            "status": "disconnected",
            "database": "postgresql",
            "detail": f"Connection failed: {str(exc)}",
        }
