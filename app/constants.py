# auth & utility
MAIN_PAGE_URL = "https://journal.top-academy.ru"
LOGIN_PAGE_URL = "https://journal.top-academy.ru/auth/login/index"
AUTH_API_URL = "https://msapi.top-academy.ru/api/v2/auth/login"
DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://journal.top-academy.ru",
    "Referer": "https://journal.top-academy.ru",
    "Content-Type": "application/json"
}

# get / post data
GET_STREAM_LEADERS_URL = "https://msapi.top-academy.ru/api/v2/dashboard/progress/leader-stream"
GET_CURRENT_SCHEDULE_URL = "https://msapi.top-academy.ru/api/v2/schedule/operations/get-by-date?date_filter="