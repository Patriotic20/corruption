from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    name: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255))  # lowercase, without "@"
    role: Mapped[str] = mapped_column(String(20), default="admin")  # super | admin
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AdminInvite(Base):
    __tablename__ = "admin_invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True)  # lowercase, without "@"
    invited_by: Mapped[int | None] = mapped_column(ForeignKey("admins.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    username: Mapped[str | None] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)
    media_url: Mapped[str | None] = mapped_column(String(500))
    media_type: Mapped[str | None] = mapped_column(String(20))  # photo | video | document
    status: Mapped[str] = mapped_column(String(50), default="new")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    replies: Mapped[list["Reply"]] = relationship(back_populates="report")


class Reply(Base):
    __tablename__ = "replies"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"))
    admin_id: Mapped[int] = mapped_column(ForeignKey("admins.id"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    report: Mapped["Report"] = relationship(back_populates="replies")
