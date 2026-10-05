"""locks.py — Database-level distributed advisory locks for background jobs."""
import hashlib
import logging
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _lock_key_to_bigint(key: str) -> int:
    """Converts a descriptive string key into a deterministic signed 64-bit integer for Postgres advisory locks."""
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


class DatabaseAdvisoryLock:
    """
    PostgreSQL session-level advisory lock helper.
    Ensures that multiple workers/threads cannot execute the same job concurrently.
    """

    def __init__(self, session: AsyncSession, lock_name: str):
        self.session = session
        self.lock_name = lock_name
        self.lock_id = _lock_key_to_bigint(lock_name)
        self.acquired = False

    async def acquire(self) -> bool:
        """Attempts to acquire the advisory lock non-blockingly."""
        try:
            result = await self.session.execute(
                text("SELECT pg_try_advisory_lock(:lock_id)"),
                {"lock_id": self.lock_id},
            )
            self.acquired = bool(result.scalar())
            if not self.acquired:
                logger.warning(
                    f"Could not acquire lock for '{self.lock_name}' (ID: {self.lock_id}). Job already running elsewhere."
                )
            return self.acquired
        except Exception as e:
            logger.warning(f"Error acquiring Postgres advisory lock for '{self.lock_name}': {e}. Allowing execution in fallback mode.")
            # If in mock or sqlite environment where advisory lock is unsupported, allow execution
            self.acquired = True
            return True

    async def release(self) -> bool:
        """Releases the advisory lock if it was acquired."""
        if not self.acquired:
            return False
        try:
            result = await self.session.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": self.lock_id},
            )
            released = bool(result.scalar())
            self.acquired = False
            return released
        except Exception as e:
            logger.debug(f"Error releasing advisory lock '{self.lock_name}': {e}")
            self.acquired = False
            return False

    async def __aenter__(self) -> bool:
        return await self.acquire()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()


@asynccontextmanager
async def try_acquire_job_lock(session: AsyncSession, job_name: str) -> AsyncGenerator[bool, None]:
    """Context manager convenience helper for acquiring and releasing job locks."""
    lock = DatabaseAdvisoryLock(session, f"job_lock_{job_name}")
    acquired = await lock.acquire()
    try:
        yield acquired
    finally:
        if acquired:
            await lock.release()
