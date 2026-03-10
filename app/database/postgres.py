from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import config


engine = create_async_engine(str(config.POSTGRES_URL), echo=True)


session_maker = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db():
    async with session_maker() as session:
        yield session
