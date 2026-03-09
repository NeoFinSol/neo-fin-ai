from datetime import datetime

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

from project import Project


class User(Base):
	__tablename__ = "users"

	id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
	login: Mapped[str] = mapped_column(String(255), unique=True, index=True)
	hashed_password: Mapped[str] = mapped_column(String(128))
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
	updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

	# Getters
	projects: Mapped[list[Project]] = relationship(back_populates="owner")
