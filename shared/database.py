from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(dsn: str) -> None:
    global _engine, _session_factory
    _engine = create_async_engine(dsn, echo=False)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if _session_factory is None:
        raise RuntimeError("DB not initialized. Call init_db() first.")
    async with _session_factory() as session:
        yield session
