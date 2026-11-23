import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import IdMixin, TimestampMixin


class CtfEvent(IdMixin, TimestampMixin, Base):
    __tablename__ = "ctf_events"
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="active")
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"))
    challenges: Mapped[list["CtfChallenge"]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class CtfChallenge(IdMixin, TimestampMixin, Base):
    __tablename__ = "ctf_challenges"
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ctf_events.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(50))
    difficulty: Mapped[str] = mapped_column(String(20), default="easy")
    points: Mapped[int] = mapped_column(Integer, default=100)
    flag_hash: Mapped[str] = mapped_column(String(128))
    lab_slug: Mapped[str | None] = mapped_column(String(100))


class CtfSubmission(IdMixin, TimestampMixin, Base):
    __tablename__ = "ctf_submissions"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    challenge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ctf_challenges.id", ondelete="CASCADE"), index=True)
    submitted_flag_hash: Mapped[str] = mapped_column(String(128))
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
