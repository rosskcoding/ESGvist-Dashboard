from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

_connect_args: dict = {}
# PostgreSQL: enforce 30s statement timeout to prevent runaway queries
if "postgresql" in settings.database_url:
    _connect_args["server_settings"] = {"statement_timeout": "30000"}  # ms

engine = create_async_engine(
    settings.database_url,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_timeout=10,  # seconds to wait for a connection from pool
    echo=settings.debug,
    connect_args=_connect_args,
)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
