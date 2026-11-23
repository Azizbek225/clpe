import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import IdMixin, SoftDeleteMixin, TimestampMixin


class Category(IdMixin, TimestampMixin, Base):
    __tablename__ = "categories"
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(50), default="shield")


class Course(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Kurs = spetsifikatsiyadagi ta'lim yo'nalishi (masalan, 03 Networking Fundamentals)."""
    __tablename__ = "courses"
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    code: Mapped[str] = mapped_column(String(10), default="")
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categories.id"))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    objectives: Mapped[list] = mapped_column(JSON, default=list)
    difficulty: Mapped[str] = mapped_column(String(20), default="beginner")
    status: Mapped[str] = mapped_column(String(20), default="published")
    estimated_duration: Mapped[int] = mapped_column(Integer, default=0)  # daqiqa
    translations: Mapped[dict] = mapped_column(JSON, default=dict)  # {"ru": {"title":..,"description":..}}
    modules: Mapped[list["Module"]] = relationship(
        back_populates="course", order_by="Module.sequence_number", cascade="all, delete-orphan"
    )


class Module(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "modules"
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(100), default="")
    title: Mapped[str] = mapped_column(String(200))
    level: Mapped[str] = mapped_column(String(20), default="beginner")
    sequence_number: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[str] = mapped_column(Text, default="")
    translations: Mapped[dict] = mapped_column(JSON, default=dict)
    course: Mapped[Course] = relationship(back_populates="modules")
    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="module", order_by="Lesson.sequence_number", cascade="all, delete-orphan"
    )


class Lesson(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "lessons"
    module_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(100), default="")
    title: Mapped[str] = mapped_column(String(200))
    lesson_type: Mapped[str] = mapped_column(String(20), default="theory")  # theory | video | lab | quiz
    content: Mapped[str] = mapped_column(Text, default="")  # Markdown
    video_url: Mapped[str | None] = mapped_column(String(500))
    lab_slug: Mapped[str | None] = mapped_column(String(100))  # lesson_type=lab bo'lsa
    duration: Mapped[int] = mapped_column(Integer, default=10)
    sequence_number: Mapped[int] = mapped_column(Integer, default=1)
    module: Mapped[Module] = relationship(back_populates="lessons")
    translations: Mapped[list["LessonTranslation"]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class LessonTranslation(IdMixin, TimestampMixin, Base):
    __tablename__ = "lesson_translations"
    __table_args__ = (UniqueConstraint("lesson_id", "language_code"),)
    lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    language_code: Mapped[str] = mapped_column(String(5))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, default="")


class Enrollment(IdMixin, TimestampMixin, Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("user_id", "course_id"),)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="active")


class LearningProgress(IdMixin, TimestampMixin, Base):
    __tablename__ = "learning_progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id"),)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    completion_status: Mapped[str] = mapped_column(String(20), default="completed")
    completion_percentage: Mapped[int] = mapped_column(Integer, default=100)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Quiz(IdMixin, TimestampMixin, Base):
    __tablename__ = "quizzes"
    module_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    passing_score: Mapped[int] = mapped_column(Integer, default=70)
    questions: Mapped[list["Question"]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class Question(IdMixin, TimestampMixin, Base):
    __tablename__ = "questions"
    quiz_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), index=True)
    question_text: Mapped[str] = mapped_column(Text)
    question_type: Mapped[str] = mapped_column(String(20), default="single")  # single | multiple
    difficulty: Mapped[str] = mapped_column(String(20), default="beginner")
    options: Mapped[list["AnswerOption"]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class AnswerOption(IdMixin, Base):
    __tablename__ = "answer_options"
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    answer_text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)


class QuizAttempt(IdMixin, TimestampMixin, Base):
    __tablename__ = "quiz_attempts"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    quiz_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"))
    score: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Certificate(IdMixin, TimestampMixin, Base):
    __tablename__ = "certificates"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"))
    certificate_number: Mapped[str] = mapped_column(String(40), unique=True)
    verification_code: Mapped[str] = mapped_column(String(64), unique=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
