import datetime
from pprint import pprint
from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import HTTPError

from app import constants as const
from app.config import config
from app.logger import logger


class Session:
    def __init__(self, username, password):
        logger.info("Session created!")
        self.payload = {
            "application_key": config.get("APP_KEY"),
            "id_city": None,
            "username": username,
            "password": password,
        }
        self.logged_in = False
        self.token: str | None = None
        self.session = AsyncSession()

    @property
    def api_headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://journal.top-academy.ru",
            "Referer": "https://journal.top-academy.ru",
        }
    async def login(self):
        if self.logged_in:
            logger.warn("already logged in, skipping...")
            return
        await self.session.get(const.LOGIN_PAGE_URL, impersonate="chrome120")

        response = await self.session.post(
            const.AUTH_API_URL,
            json=self.payload,
            headers=const.DEFAULT_HEADERS,
            impersonate="chrome120"
        )
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")
            self.logged_in = True
            logger.info("successfully logged in!")
        else:
            raise HTTPError
            
    async def get_leaderboard(self):
        logger.info("trying to get leaderboard")
        if not self.logged_in:
            logger.warn("not logged in, trying to log in...")
            await self.login()
            
        self.api_headers["Authorization"] = f"Bearer {self.token}"
        
        response = await self.session.get(
            const.GET_STREAM_LEADERS_URL,
            headers=self.api_headers,
            impersonate="chrome120"
        )
        if response.status_code == 200:
            logger.info("successfully got data from leaderbord endpoint")
            data = response.json()
            return data
        elif response.status_code == 401:
            logger.error("401 error code, trying to log in again...")
            self.logged_in = False
            await self.login()
            return self.get_leaderboard()
    
    async def get_current_schedule(self) -> list[dict]:
        if not self.logged_in:
            logger.warn("not logged in, trying to log in...")
            await self.login()
        
        self.api_headers["Authorization"] = f"Bearer {self.token}"
        
        current_date = str(datetime.datetime.now().date())
        url = const.GET_CURRENT_SCHEDULE_URL+current_date
        
        response = await self.session.get(
            url,
            headers=self.api_headers,
            impersonate="chrome120"
        )
        if response.status_code == 200:
            logger.info(f"successfully got data from schedule endpoint")
            data = response.json()
            return data
        elif response.status_code == 401:
            logger.error("401 error code, trying to log in again...")
            self.logged_in = False
            await self.login()
            return await self.get_current_schedule()
        return []
