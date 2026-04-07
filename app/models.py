from sqlalchemy import String, Integer, BigInteger, ForeignKey, Date
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    telegram_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, unique=True, index=True
    )
    telegram_username: Mapped[str] = mapped_column(String, unique=True, index=True)

    journal_login: Mapped[str] = mapped_column(String, unique=True, nullable=True)
    journal_password: Mapped[str] = mapped_column(String, nullable=True)

    group: Mapped[str] = mapped_column(String, index=True, nullable=True)
    
    favorite_homeworks: Mapped[list["FavoriteHomework"]] = relationship(
        "FavoriteHomework", back_populates="user", cascade="all, delete-orphan"
    )

# пока не использую
class FavoriteHomework(Base):
    __tablename__ = "favorite_homeworks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    homework_lesson_name: Mapped[str] = mapped_column(String, nullable=False)
    homework_name: Mapped[str] = mapped_column(String, nullable=False)
    homework_id: Mapped[int] = mapped_column(Integer, nullable=False)
    
    homework_uploaded_at: Mapped[Date] = mapped_column(Date, nullable=False)
    expires_at: Mapped[Date] = mapped_column(Date, nullable=False)
    
    user: Mapped["User"] = relationship("User", back_populates="favorite_homeworks")
