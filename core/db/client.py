import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Async DB URL required for async engine
db_url = os.getenv("ASYNC_DATABASE_URL")
if not db_url:
    raise RuntimeError("ASYNC_DATABASE_URL is not set. Please define it in your .env file.")

# Create async engine
engine = create_async_engine(
    db_url,
    future=True,
    echo=False,
)

# Create async session factory
async_session = sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

async def get_db_session():
    async with async_session() as session:
        yield session
