from sqlalchemy import String, Integer, BigInteger
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    telegram_username: Mapped[str] = mapped_column(String, unique=True, index=True)
    
    journal_login: Mapped[str] = mapped_column(String, unique=True, nullable=True)
    journal_password: Mapped[str] = mapped_column(String, nullable=True)
    
    journal_token: Mapped[str] = mapped_column(String)