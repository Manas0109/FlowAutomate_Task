from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,  # Verify connections before using them
    pool_size=20,  # Number of connections to keep in the pool
    max_overflow=10,  # Allow temporary overflow beyond pool_size
    pool_recycle=3600,  # Recycle connections after 1 hour
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session (for use with Depends() in FastAPI)."""
    async with SessionLocal() as session:
        yield session


async def get_db() -> AsyncSession:
    """Get a database session (for direct use in non-FastAPI code like WebSocket).
    
    Close this session when done using it:
       db = await get_db()
       try:
           # ... use db ...
       finally:
           await db.close()
    """
    return SessionLocal()


async def check_db_health() -> bool:
    """Check if database is reachable."""
    async with engine.begin() as conn:
        await conn.execute("SELECT 1")
    return True