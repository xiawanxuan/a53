from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from ..config.settings import settings
from typing import AsyncGenerator


class BaseMySQL(DeclarativeBase):
    pass


class BaseTimescale(DeclarativeBase):
    pass


mysql_engine = create_async_engine(
    settings.get_mysql_url(),
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=50,
    echo=False,
)

timescale_engine = create_async_engine(
    settings.get_timescale_url(),
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=50,
    echo=False,
)

MySQLSessionLocal = async_sessionmaker(
    mysql_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

TimescaleSessionLocal = async_sessionmaker(
    timescale_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_mysql_session() -> AsyncGenerator[AsyncSession, None]:
    async with MySQLSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_timescale_session() -> AsyncGenerator[AsyncSession, None]:
    async with TimescaleSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
