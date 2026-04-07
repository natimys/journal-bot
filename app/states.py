from aiogram.fsm.state import State, StatesGroup


class LoginStates(StatesGroup):
    waiting_for_login = State()
    waiting_for_password = State()


class HomeworkUpload(StatesGroup):
    waiting_for_files = State()
