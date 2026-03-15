import io
import asyncio
import time
from typing import Literal

from curl_cffi import CurlMime
from curl_cffi.requests import AsyncSession
from redis.asyncio import Redis

from app import constants as const
from app.config import config
from app.logger import logger

_last_request_time = 0
_request_lock = asyncio.Lock()
api_semaphore = asyncio.Semaphore(3)


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
            logger.error(
                f"Login request failed for {self.username!r}: {err} status={response.status_code} body={text}"
            )
            raise

        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")

            if not self.token:
                logger.error(
                    f"Login succeeded but no access_token returned for {self.username!r}"
                )
                raise RuntimeError("Missing access token from login response")

            await self.redis.set(f"user:{self.telegram_id}:token", self.token, ex=1800)

            self.logged_in = True
            logger.info(f"User {self.username!r} successfully logged in!")

    async def get_info(self) -> dict:
        return await self._make_request(const.GET_USER_INFO_URL)

    async def _make_request(
        self, url: str, method: Literal["GET", "POST"] = "GET", retries=3, **kwargs
    ) -> dict:
        """Создание запросов на API журнала

        Args:
            url (str): URL куда слать запрос, добавляйте пожалуйста константы в constants.py
            method (Literal[&quot;GET&quot;, &quot;POST&quot;]): Метод запроса, автоматически стоит GET

        Returns:
            dict: Возвращает json ответа от сервера в виде словаря
        """
        global _last_request_time
        async with api_semaphore:
            async with _request_lock:
                now = time.time()
                delta = now - _last_request_time
                if delta < 0.5:
                    await asyncio.sleep(0.5 - delta)
                _last_request_time = time.time()

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
                    method, url, headers=current_headers, timeout=15, **kwargs
                )

                if response.status_code == 429:
                    if retries > 0:
                        logger.warning(f"429 hit. Retrying... ({retries} left)")
                        await asyncio.sleep(10)
                        return await self._make_request(
                            url, method, retries=retries - 1, **kwargs
                        )
                    else:
                        logger.error("Max retries reached for 429. Giving up.")
                        raise Exception("API rate limit exceeded")

                response.raise_for_status()
                return response.json()
            except Exception as e:
                if getattr(e, "code", None) == 429:
                    await asyncio.sleep(5)
                    return await self._make_request(url, method, **kwargs)
                raise

    async def close(self):
        await self._http_session.close()

    async def upload_homework(
        self, zip_data: io.BytesIO, filename: str, homework_id: int
    ):
        if not self.token:
            cached_token = await self.redis.get(f"user:{self.telegram_id}:token")
            if cached_token:
                self.token = cached_token.decode()
            else:
                await self.login()

        headers = self.api_headers.copy()
        headers.pop("Content-Type", None)

        logger.info(f"Uploading with token starting with: {self.token[:10]}...")

        mp_create = CurlMime()
        mp_create.addpart(name="id", data=str(homework_id))
        mp_create.addpart(
            name="file",
            filename=filename,
            content_type="application/zip",
            data=zip_data.getvalue(),
        )

        try:
            response_create = await self._http_session.post(
                const.CREATE_HOMEWORK_URL,
                headers=headers,
                multipart=mp_create,
                timeout=60,
            )

            if response_create.status_code == 401:
                logger.error(
                    "401 Unauthorized during CREATE. Trying to re-login and retry..."
                )
                await self.login()
                headers["Authorization"] = f"Bearer {self.token}"
                response_create = await self._http_session.post(
                    const.CREATE_HOMEWORK_URL,
                    headers=headers,
                    multipart=mp_create,
                    timeout=60,
                )

            response_create.raise_for_status()
            create_data = response_create.json()
            internal_file_id = create_data.get("id")

        finally:
            mp_create.close()

        import json

        save_payload = {
            "id": internal_file_id,
            "idDomZad": homework_id,
            "idStud": None,
            "mark": 0,
            "comment": "Sent via Bot",
            "tags": [],
        }

        mp_save = CurlMime()
        mp_save.addpart(name="EvaluationHomeworkForm", data=json.dumps(save_payload))

        try:
            response_save = await self._http_session.post(
                const.SAVE_HOMEWORK_URL, headers=headers, multipart=mp_save
            )
            response_save.raise_for_status()
            return response_save.json()
        finally:
            mp_save.close()
