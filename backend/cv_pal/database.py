from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from cv_pal.config import get_settings

engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession]:
    """Provide a transactional database session scope.

    Yields:
        An async SQLAlchemy session, automatically closed after use.
    """
    async with async_session() as session:
        yield session
