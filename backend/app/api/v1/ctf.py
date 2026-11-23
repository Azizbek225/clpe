import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import audit, get_current_user, require
from app.core.security import flags_equal, hash_flag
from app.db import get_db
from app.models import CtfChallenge, CtfEvent, CtfSubmission, User
from app.services.progress import award_xp

router = APIRouter(prefix="/ctf", tags=["ctf"])


def _solved(db: Session, user_id) -> set:
    return set(db.scalars(select(CtfSubmission.challenge_id).where(CtfSubmission.user_id == user_id,
                                                                   CtfSubmission.is_correct.is_(True))))


def _ch(c: CtfChallenge, solved: set, solves: dict) -> dict:
    return {"id": str(c.id), "title": c.title, "description": c.description, "category": c.category,
            "difficulty": c.difficulty, "points": c.points, "lab_slug": c.lab_slug, "solved": c.id in solved,
            "solves": solves.get(c.id, 0)}


def _solve_counts(db: Session) -> dict:
    return dict(db.execute(select(CtfSubmission.challenge_id, func.count()).where(
        CtfSubmission.is_correct.is_(True)).group_by(CtfSubmission.challenge_id)).all())


@router.get("/events")
def events(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return [{"id": str(e.id), "slug": e.slug, "title": e.title, "description": e.description, "status": e.status,
             "start_time": e.start_time, "end_time": e.end_time, "challenges": len(e.challenges)}
            for e in db.scalars(select(CtfEvent))]


@router.get("/events/{event_id}")
def event(event_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    e = db.get(CtfEvent, event_id)
    if not e:
        raise HTTPException(404, "Tadbir topilmadi")
    solved, counts = _solved(db, user.id), _solve_counts(db)
    return {"id": str(e.id), "title": e.title, "description": e.description, "status": e.status,
            "challenges": [_ch(c, solved, counts) for c in sorted(e.challenges, key=lambda c: (c.category, c.points))]}


@router.get("/challenges")
def challenges(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    solved, counts = _solved(db, user.id), _solve_counts(db)
    return [_ch(c, solved, counts) for c in db.scalars(select(CtfChallenge).order_by(CtfChallenge.points))]


class FlagIn(BaseModel):
    flag: str = Field(..., max_length=200)


@router.post("/challenges/{challenge_id}/submit")
def submit(challenge_id: uuid.UUID, body: FlagIn, request: Request, user: User = Depends(require("ctf:play")),
           db: Session = Depends(get_db)) -> dict:
    c = db.get(CtfChallenge, challenge_id)
    if not c:
        raise HTTPException(404, "Challenge topilmadi")
    ev = db.get(CtfEvent, c.event_id)
    nowt = datetime.now(timezone.utc)
    if ev.status != "active" or (ev.end_time and ev.end_time.replace(tzinfo=ev.end_time.tzinfo or timezone.utc) < nowt):
        raise HTTPException(409, "Tadbir faol emas")
    recent = db.scalar(select(func.count()).select_from(CtfSubmission).where(
        CtfSubmission.user_id == user.id, CtfSubmission.challenge_id == c.id, CtfSubmission.is_correct.is_(False)))
    if recent and recent >= 30:
        raise HTTPException(429, "Urinishlar soni chegaradan oshdi")
    if c.id in _solved(db, user.id):
        return {"correct": True, "already_solved": True, "points": 0}
    ok = flags_equal(body.flag, c.flag_hash)
    db.add(CtfSubmission(user_id=user.id, challenge_id=c.id, submitted_flag_hash=hash_flag(body.flag), is_correct=ok))
    if ok:
        award_xp(db, user.id, c.points)
    audit(db, user, "ctf.submit", "ctf_challenge", str(c.id), request, "correct" if ok else "wrong")
    db.commit()
    return {"correct": ok, "points": c.points if ok else 0}


@router.get("/leaderboard")
def leaderboard(event_id: uuid.UUID | None = None, _: User = Depends(get_current_user),
                db: Session = Depends(get_db)) -> list[dict]:
    q = (select(User.username, func.sum(CtfChallenge.points).label("pts"), func.count().label("solves"),
                func.max(CtfSubmission.created_at).label("last"))
         .join(CtfSubmission, CtfSubmission.user_id == User.id)
         .join(CtfChallenge, CtfChallenge.id == CtfSubmission.challenge_id)
         .where(CtfSubmission.is_correct.is_(True)).group_by(User.username)
         .order_by(func.sum(CtfChallenge.points).desc(), func.max(CtfSubmission.created_at)))
    if event_id:
        q = q.where(CtfChallenge.event_id == event_id)
    return [{"rank": i + 1, "username": u, "points": p, "solves": s} for i, (u, p, s, _l) in enumerate(db.execute(q).all())]


class ChallengeIn(BaseModel):
    event_id: uuid.UUID
    title: str
    description: str = ""
    category: str
    difficulty: str = "easy"
    points: int = 100
    flag: str
    lab_slug: str | None = None


@router.post("/challenges", status_code=201)
def create_challenge(body: ChallengeIn, user: User = Depends(require("ctf:manage")), db: Session = Depends(get_db)) -> dict:
    if not db.get(CtfEvent, body.event_id):
        raise HTTPException(404, "Tadbir topilmadi")
    c = CtfChallenge(**body.model_dump(exclude={"flag"}), flag_hash=hash_flag(body.flag))
    db.add(c)
    audit(db, user, "ctf.challenge.create", "ctf_challenge", body.title)
    db.commit()
    return {"id": str(c.id)}
