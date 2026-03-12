from typing import Literal

from curl_cffi.requests import AsyncSession

from app import constants as const
from app.config import config
from app.logger import logger
from redis.asyncio import Redis


class JournalClient:
    """Клиент для связи с апишкой журнала, логинится из под аккаунта студента

    Attributes:
        username (str): Логин от журнала
        password (str): Пароль от журнала
        telegram_id (int): Telegram ID пользователя
        redis_client (Redis): Redis
    """

    def __init__(
        self, username: str, password: str, telegram_id: int, redis_client: Redis
    ):
        self.username = username
        self.password = password
        self.telegram_id = telegram_id
        self.logged_in = False
        self.token: str | None = None
        self._http_session = AsyncSession(impersonate="chrome120")
        self.redis = redis_client

    @property
    def api_headers(self):  # эта штука нужна чтобы автоматически токен обновлять
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://journal.top-academy.ru",
            "Referer": "https://journal.top-academy.ru",
        }

    async def login(self):
        """Логин от лица пользователя в журнал
        В том случае если при создании клиента журнал отдает 200, то сохраняет данные пользователя
        """
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

        try:
            response.raise_for_status()
        except Exception as err:
            text = None
            try:
                text = response.text
            except Exception:
                pass
            if response.status_code == 429:
                logger.warning(f"Rate limited when logging in user {self.username!r}")
            logger.error(f"Login request failed for {self.username!r}: {err} status={response.status_code} body={text}")
            raise

        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")

            if not self.token:
                logger.error(f"Login succeeded but no access_token returned for {self.username!r}")
                raise RuntimeError("Missing access token from login response")

            await self.redis.set(f"user:{self.telegram_id}:token", self.token, ex=36000)

            self.logged_in = True
            logger.info(f"User {self.username!r} successfully logged in!")
            
    async def get_info(self) -> dict:
        return await self._make_request(const.GET_USER_INFO_URL)
    
    async def _make_request(
        self, url: str, method: Literal["GET", "POST"] = "GET", **kwargs
    ) -> dict:
        """Создание запросов на API журнала

        Args:
            url (str): URL куда слать запрос, добавляйте пожалуйста константы в constants.py
            method (Literal[&quot;GET&quot;, &quot;POST&quot;]): Метод запроса, автоматически стоит GET

        Returns:
            dict: Возвращает json ответа от сервера в виде словаря
        """

        if not self.token:
            cached_token = await self.redis.get(f"user:{self.telegram_id}:token")
            if cached_token:
                self.token = cached_token.decode()
                self.logged_in = True
        if not self.token:
            await self.login()

        current_headers = {**self.api_headers, **kwargs.pop("headers", {})}

        try:
            response = await self._http_session.request(
                method, url, headers=current_headers, timeout=10, **kwargs
            )
        except Exception as e:
            logger.error(f"HTTP request error to {url}: {e}")
            raise

        if response.status_code == 401: # авторелогин если токен юзера истек
            logger.warning("Token expired, retrying login...")
            self.logged_in = False
            await self.login()
            response = await self._http_session.request(
                method, url, headers=self.api_headers, timeout=10, **kwargs
            )

        try:
            response.raise_for_status()  # автоматически вызывает исключение если произошла ошибка
        except Exception as err:
            text = None
            try:
                text = response.text
            except Exception:
                pass
            logger.error(f"API request to {url} failed: {err} status={response.status_code} body={text}")
            raise
        return response.json()

    async def close(self):
        await self._http_session.close()
