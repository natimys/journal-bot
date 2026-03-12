# auth & utility
MAIN_PAGE_URL = "https://journal.top-academy.ru"
LOGIN_PAGE_URL = "https://journal.top-academy.ru/auth/login/index"
AUTH_API_URL = "https://msapi.top-academy.ru/api/v2/auth/login"
DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://journal.top-academy.ru",
    "Referer": "https://journal.top-academy.ru",
    "Content-Type": "application/json",
}

# get / post data
GET_STREAM_LEADERS_URL = (
    "https://msapi.top-academy.ru/api/v2/dashboard/progress/leader-stream"
)
GET_SCHEDULE_BY_DATE_URL = (
    "https://msapi.top-academy.ru/api/v2/schedule/operations/get-by-date?date_filter="
)
GET_AVERAGE_SCORE_URL = (
    "https://msapi.top-academy.ru/api/v2/dashboard/chart/average-progress"
)

GET_HOMEWORKS_URL = (
    "https://msapi.top-academy.ru/api/v2/homework/operations/list?page={page}&status={status}&type=0&group_id={group_id}"
)
"""URL для получения дз с различными статусами  
### page
счёт начинается с 1  
### status:
0 - истекшие  
1 - проверенные  
2 - на проверке  
3 - активные  
5 - удаленные  

4 почему то нету  
### group_id
РПО - 3
КГиД - неизвестно
### usage:
    GET_HOMEWORKS_URL.format(page=1, status=0, group_id=3)
"""

GET_USER_INFO_URL = (
    "https://msapi.top-academy.ru/api/v2/settings/user-info"
)