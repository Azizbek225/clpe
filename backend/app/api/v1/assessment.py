import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require
from app.db import get_db
from app.models import (
    AnswerOption, Certificate, Course, LabInstance, LabSubmission, Module, Question, Quiz, QuizAttempt, User,
)
from app.services.progress import award_xp, course_completion, maybe_issue_certificate

router = APIRouter(tags=["assessment"])


def quiz_public(q: Quiz) -> dict:
    return {"id": str(q.id), "module_id": str(q.module_id), "title": q.title, "passing_score": q.passing_score,
            "questions": [{"id": str(x.id), "text": x.question_text, "type": x.question_type, "difficulty": x.difficulty,
                           "options": [{"id": str(o.id), "text": o.answer_text} for o in x.options]}
                          for x in q.questions]}


@router.get("/quizzes")
def list_quizzes(module_id: uuid.UUID | None = None, _: User = Depends(get_current_user),
                 db: Session = Depends(get_db)) -> list[dict]:
    q = select(Quiz)
    if module_id:
        q = q.where(Quiz.module_id == module_id)
    return [{"id": str(x.id), "module_id": str(x.module_id), "title": x.title, "questions": len(x.questions)}
            for x in db.scalars(q)]


@router.get("/quizzes/{quiz_id}")
def get_quiz(quiz_id: uuid.UUID, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    q = db.get(Quiz, quiz_id)
    if not q:
        raise HTTPException(404, "Test topilmadi")
    return quiz_public(q)


@router.post("/quizzes/{quiz_id}/start")
def start_quiz(quiz_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    q = db.get(Quiz, quiz_id)
    if not q:
        raise HTTPException(404, "Test topilmadi")
    att = QuizAttempt(user_id=user.id, quiz_id=q.id, started_at=datetime.now(timezone.utc))
    db.add(att)
    db.commit()
    return {"attempt_id": str(att.id), **quiz_public(q)}


class QuizSubmit(BaseModel):
    attempt_id: uuid.UUID | None = None
    answers: dict[str, list[str]]  # question_id -> [option_id]


@router.post("/quizzes/{quiz_id}/submit")
def submit_quiz(quiz_id: uuid.UUID, body: QuizSubmit, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)) -> dict:
    q = db.get(Quiz, quiz_id)
    if not q:
        raise HTTPException(404, "Test topilmadi")
    correct = 0
    review = []
    for question in q.questions:
        right = {str(o.id) for o in question.options if o.is_correct}
        given = set(body.answers.get(str(question.id), []))
        ok = given == right
        correct += ok
        review.append({"question_id": str(question.id), "correct": ok, "correct_options": sorted(right)})
    score = round(100 * correct / len(q.questions)) if q.questions else 0
    passed = score >= q.passing_score
    att = db.get(QuizAttempt, body.attempt_id) if body.attempt_id else None
    if not att or att.user_id != user.id:
        att = QuizAttempt(user_id=user.id, quiz_id=q.id, started_at=datetime.now(timezone.utc))
        db.add(att)
    already = db.scalar(select(QuizAttempt).where(QuizAttempt.user_id == user.id, QuizAttempt.quiz_id == q.id,
                                                  QuizAttempt.passed.is_(True)))
    att.score, att.passed, att.completed_at = score, passed, datetime.now(timezone.utc)
    if passed and not already:
        award_xp(db, user.id, 50)
    db.commit()
    module = db.get(Module, q.module_id)
    cert = maybe_issue_certificate(db, user.id, module.course_id) if passed else None
    return {"score": score, "passed": passed, "correct": correct, "total": len(q.questions), "review": review,
            "certificate": cert}


class QuestionIn(BaseModel):
    text: str
    type: str = "single"
    difficulty: str = "beginner"
    options: list[str]
    correct: list[int]


class QuizIn(BaseModel):
    module_id: uuid.UUID | None = None
    title: str
    passing_score: int = 70
    questions: list[QuestionIn]


@router.put("/quizzes/{quiz_id}")
def update_quiz(quiz_id: uuid.UUID, body: QuizIn, _: User = Depends(require("quiz:write")),
                db: Session = Depends(get_db)) -> dict:
    q = db.get(Quiz, quiz_id)
    if not q:
        raise HTTPException(404, "Test topilmadi")
    _fill_quiz(db, q, body)
    return quiz_public(q)


@router.post("/quizzes", status_code=201)
def create_quiz(body: QuizIn, _: User = Depends(require("quiz:write")), db: Session = Depends(get_db)) -> dict:
    if not body.module_id or not db.get(Module, body.module_id):
        raise HTTPException(422, "module_id noto'g'ri")
    q = Quiz(module_id=body.module_id, title=body.title)
    db.add(q)
    db.flush()
    _fill_quiz(db, q, body)
    return quiz_public(q)


@router.get("/quizzes/{quiz_id}/edit")
def quiz_for_edit(quiz_id: uuid.UUID, _: User = Depends(require("quiz:write")), db: Session = Depends(get_db)) -> dict:
    q = db.get(Quiz, quiz_id)
    if not q:
        raise HTTPException(404, "Test topilmadi")
    return {"id": str(q.id), "module_id": str(q.module_id), "title": q.title, "passing_score": q.passing_score,
            "questions": [{"text": x.question_text, "type": x.question_type, "difficulty": x.difficulty,
                           "options": [o.answer_text for o in x.options],
                           "correct": [i for i, o in enumerate(x.options) if o.is_correct]} for x in q.questions]}


def _fill_quiz(db: Session, q: Quiz, body: QuizIn) -> None:
    q.title, q.passing_score = body.title, body.passing_score
    q.questions.clear()
    db.flush()
    for qq in body.questions:
        if not qq.correct or any(i >= len(qq.options) for i in qq.correct):
            raise HTTPException(422, f"'{qq.text[:40]}': to'g'ri javob indekslari noto'g'ri")
        question = Question(quiz_id=q.id, question_text=qq.text, question_type=qq.type, difficulty=qq.difficulty)
        question.options = [AnswerOption(answer_text=o, is_correct=i in qq.correct) for i, o in enumerate(qq.options)]
        q.questions.append(question)
    db.commit()
    db.refresh(q)


@router.get("/results")
def results(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    quizzes = db.execute(select(QuizAttempt, Quiz.title).join(Quiz).where(
        QuizAttempt.user_id == user.id, QuizAttempt.completed_at.is_not(None))
        .order_by(QuizAttempt.completed_at.desc()).limit(50)).all()
    labs = db.scalars(select(LabInstance).where(LabInstance.user_id == user.id)
                      .order_by(LabInstance.created_at.desc()).limit(50)).all()
    return {
        "quizzes": [{"quiz": t, "score": a.score, "passed": a.passed, "completed_at": a.completed_at} for a, t in quizzes],
        "labs": [{"lab": i.template.slug, "title": i.template.name, "score": i.score, "status": i.status,
                  "started_at": i.started_at} for i in labs],
    }


@router.get("/progress")
def progress(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    out = []
    for c in db.scalars(select(Course).where(Course.status == "published", Course.deleted_at.is_(None))
                        .order_by(Course.code)):
        done, total, quizzes_ok = course_completion(db, user.id, c.id)
        out.append({"course_id": str(c.id), "slug": c.slug, "title": c.title, "completed": done, "total": total,
                    "percent": round(100 * done / total) if total else 0, "quizzes_passed": quizzes_ok})
    lab_pts = db.scalar(select(func.coalesce(func.sum(LabSubmission.score), 0)).where(
        LabSubmission.user_id == user.id, LabSubmission.passed.is_(True))) or 0
    return {"xp": user.xp, "level": user.level, "next_level_xp": user.level * 500, "lab_points": lab_pts,
            "courses": out}


@router.get("/certificates")
def certificates(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(select(Certificate, Course.title).join(Course).where(Certificate.user_id == user.id)).all()
    return [{"number": c.certificate_number, "course": t, "issued_at": c.issued_at,
             "verification_code": c.verification_code} for c, t in rows]


@router.get("/certificates/verify/{code}")
def verify_certificate(code: str, db: Session = Depends(get_db)) -> dict:
    row = db.execute(select(Certificate, Course.title, User.full_name, User.username).join(Course)
                     .join(User, User.id == Certificate.user_id).where(Certificate.verification_code == code)).first()
    if not row:
        raise HTTPException(404, "Sertifikat topilmadi")
    c, title, full_name, username = row
    return {"valid": True, "number": c.certificate_number, "course": title, "holder": full_name or username,
            "issued_at": c.issued_at}


@router.get("/leaderboard")
def leaderboard(limit: int = 20, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    users = db.scalars(select(User).where(User.deleted_at.is_(None)).order_by(User.xp.desc()).limit(min(limit, 100)))
    return [{"rank": i + 1, "username": u.username, "xp": u.xp, "level": u.level} for i, u in enumerate(users)]
