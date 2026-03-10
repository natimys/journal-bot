from .auth import router as auth_router
from .common import router as common_router
from .request import router as request_router

all_routers = [auth_router, common_router, request_router]