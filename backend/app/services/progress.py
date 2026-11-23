import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Certificate, LearningProgress, Lesson, Module, Quiz, QuizAttempt, User


def award_xp(db: Session, user_id: uuid.UUID, amount: int) -> None:
    u = db.get(User, user_id)
    if u:
        u.xp = (u.xp or 0) + amount


def course_completion(db: Session, user_id: uuid.UUID, course_id: uuid.UUID) -> tuple[int, int, bool]:
    lessons = db.scalars(select(Lesson.id).join(Module).where(
        Module.course_id == course_id, Module.deleted_at.is_(None), Lesson.deleted_at.is_(None))).all()
    done = set(db.scalars(select(LearningProgress.lesson_id).where(LearningProgress.user_id == user_id)))
    quizzes = db.scalars(select(Quiz.id).join(Module).where(Module.course_id == course_id,
                                                            Module.deleted_at.is_(None))).all()
    passed = set(db.scalars(select(QuizAttempt.quiz_id).where(QuizAttempt.user_id == user_id,
                                                              QuizAttempt.passed.is_(True))))
    completed = sum(1 for x in lessons if x in done)
    return completed, len(lessons), all(q in passed for q in quizzes)


def maybe_issue_certificate(db: Session, user_id: uuid.UUID, course_id: uuid.UUID) -> dict | None:
    existing = db.scalar(select(Certificate).where(Certificate.user_id == user_id, Certificate.course_id == course_id))
    if existing:
        return {"number": existing.certificate_number, "verification_code": existing.verification_code}
    done, total, quizzes_ok = course_completion(db, user_id, course_id)
    if total == 0 or done < total or not quizzes_ok:
        return None
    cert = Certificate(user_id=user_id, course_id=course_id, issued_at=datetime.now(timezone.utc),
                       certificate_number=f"CLPE-{datetime.now().year}-{secrets.token_hex(4).upper()}",
                       verification_code=secrets.token_urlsafe(16))
    db.add(cert)
    award_xp(db, user_id, 250)
    db.commit()
    return {"number": cert.certificate_number, "verification_code": cert.verification_code}
