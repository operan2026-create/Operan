from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# Create async engine for PostgreSQL
engine = create_async_engine(settings.DATABASE_URL, echo=settings.SQL_ECHO, future=True)

# Create session factory
async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)

# Declarative base for models
Base = declarative_base()

async def get_db():
    """
    Dependency for getting an async database session.
    Yields the session and ensures it is closed after the request.
    """
    async with async_session() as session:
        yield session
