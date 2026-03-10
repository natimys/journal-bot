from redis.asyncio import Redis

from app.config import config

redis_client: Redis = Redis.from_url(str(config.REDIS_URL))

async def close_redis():
    await redis_client.close()