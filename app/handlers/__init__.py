from .auth import router as auth_router
from .common import router as common_router
from .getters import router as getters_router

all_routers = [auth_router, common_router, getters_router]