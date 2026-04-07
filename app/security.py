from cryptography.fernet import Fernet
from app.config import config

cipher_suite = Fernet(config.SECRET_KEY.encode())


def encrypt_password(password: str) -> str:
    if not password:
        return
    return cipher_suite.encrypt(password.encode()).decode()


def decrypt_password(encrypted_password: str) -> str:
    if not encrypted_password:
        return None
    return cipher_suite.decrypt(encrypted_password.encode()).decode()
