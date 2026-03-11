from curl_cffi.requests import AsyncSession

from app import constants as const
from app.config import config
from app.logger import logger
from redis.asyncio import Redis


class JournalClient:
    def __init__(self, username, password, telegram_id, redis_client: Redis):
        self.username = username
        self.password = password
        self.telegram_id = telegram_id
        self.logged_in = False
        self.token: str | None = None
        self._http_session = AsyncSession(impersonate="chrome120")
        self.redis = redis_client

    @property
    def api_headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://journal.top-academy.ru",
            "Referer": "https://journal.top-academy.ru",
        }

    async def login(self):
        await self._http_session.get(const.LOGIN_PAGE_URL)

        payload = {
            "application_key": config.APP_KEY,
            "id_city": None,
            "username": self.username,
            "password": self.password,
        }

        response = await self._http_session.post(
            const.AUTH_API_URL, json=payload, headers=const.DEFAULT_HEADERS
        )

        response.raise_for_status()
        if response.status_code == 200:    
            data = response.json()
            self.token = data.get("access_token")

            await self.redis.set(f"user:{self.telegram_id}:token", self.token, ex=36000)
            
            self.logged_in = True
            logger.info(f"User {self.username} successfully logged in!")

    async def _make_request(self, url, method="GET", **kwargs):
        if not self.token:
            cached_token = await self.redis.get(f"user:{self.telegram_id}:token")
            if cached_token:
                self.token = cached_token.decode()
                self.logged_in = True
        if not self.token:
            await self.login()

        current_headers = {**self.api_headers, **kwargs.pop("headers", {})}

        response = await self._http_session.request(
            method, url, headers=current_headers, **kwargs
        )

        if response.status_code == 401:
            logger.warning("Token expired, retrying login...")
            self.logged_in = False
            await self.login()
            response = await self._http_session.request(
                method, url, headers=self.api_headers, **kwargs
            )

        response.raise_for_status()
        return response.json()

    async def close(self):
        await self._http_session.close()
