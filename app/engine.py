from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.config import config

DB_URL = config["DATABASE_URL"]
engine = create_async_engine(DB_URL)
session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    with session_maker() as session:
        yield session

