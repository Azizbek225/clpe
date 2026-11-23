"""Kurslar (yo'nalishlar), modullar, darslar — o'qish va tahrirlash (CRUD).
Har bir modul va dars alohida tahrirlanadi; kurs YAML paket sifatida eksport/import qilinadi."""
import uuid
from datetime import datetime, timezone

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.deps import audit, get_current_user, require, user_permissions
from app.db import get_db
from app.models import (
    Category, Course, Enrollment, LearningProgress, Lesson, LessonTranslation, Module, Quiz, User,
)
from app.services.content import export_pack, import_pack
from app.services.progress import award_xp, maybe_issue_certificate

router = APIRouter(tags=["courses"])


def _tr(obj, lang: str, field: str) -> str:
    tr = (getattr(obj, "translations", None) or {})
    if isinstance(tr, dict):
        return (tr.get(lang) or {}).get(field) or getattr(obj, field)
    return getattr(obj, field)


def _course_or_404(db: Session, key: str) -> Course:
    try:
        c = db.get(Course, uuid.UUID(key))
    except ValueError:
        c = db.scalar(select(Course).where(Course.slug == key))
    if not c or c.deleted_at:
        raise HTTPException(404, "Kurs topilmadi")
    return c


def _completed_ids(db: Session, user: User) -> set[uuid.UUID]:
    return set(db.scalars(select(LearningProgress.lesson_id).where(LearningProgress.user_id == user.id)))


def course_summary(c: Course, lang: str, done: set, cats: dict) -> dict:
    lessons = [le for m in c.modules if not m.deleted_at for le in m.lessons if not le.deleted_at]
    total = len(lessons)
    completed = sum(1 for le in lessons if le.id in done)
    return {"id": str(c.id), "slug": c.slug, "code": c.code, "title": _tr(c, lang, "title"),
            "description": _tr(c, lang, "description"), "difficulty": c.difficulty, "status": c.status,
            "estimated_duration": c.estimated_duration, "category": cats.get(c.category_id),
            "modules": sum(1 for m in c.modules if not m.deleted_at), "lessons": total,
            "labs": sum(1 for le in lessons if le.lesson_type == "lab"),
            "progress": round(100 * completed / total) if total else 0}


# ------------------------------------------------------------------ o'qish
@router.get("/categories")
def categories(db: Session = Depends(get_db)) -> list[dict]:
    return [{"id": str(c.id), "slug": c.slug, "title": c.title, "icon": c.icon} for c in db.scalars(select(Category))]


@router.get("/glossary")
def glossary() -> list[dict]:
    data = yaml.safe_load((get_settings().content_dir / "glossary.yaml").read_text(encoding="utf-8"))
    return data.get("terms", [])


@router.get("/courses")
def list_courses(lang: str = "uz", include_drafts: bool = False, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)) -> list[dict]:
    can_edit = "content:write" in user_permissions(user)
    q = select(Course).where(Course.deleted_at.is_(None)).order_by(Course.code)
    if not (include_drafts and can_edit):
        q = q.where(Course.status == "published")
    cats = {c.id: c.slug for c in db.scalars(select(Category))}
    done = _completed_ids(db, user)
    return [course_summary(c, lang, done, cats) for c in db.scalars(q)]


@router.get("/courses/{key}")
def get_course(key: str, lang: str = "uz", user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    c = _course_or_404(db, key)
    done = _completed_ids(db, user)
    cats = {x.id: x.slug for x in db.scalars(select(Category))}
    out = course_summary(c, lang, done, cats)
    out["objectives"] = c.objectives
    out["translations"] = c.translations
    out["enrolled"] = bool(db.scalar(select(Enrollment).where(Enrollment.user_id == user.id, Enrollment.course_id == c.id)))
    out["modules_detail"] = []
    for m in c.modules:
        if m.deleted_at:
            continue
        quiz = db.scalar(select(Quiz).where(Quiz.module_id == m.id))
        out["modules_detail"].append({
            "id": str(m.id), "slug": m.slug, "title": _tr(m, lang, "title"), "level": m.level,
            "description": _tr(m, lang, "description"), "sequence_number": m.sequence_number,
            "quiz": {"id": str(quiz.id), "title": quiz.title, "questions": len(quiz.questions)} if quiz else None,
            "lessons": [{"id": str(le.id), "slug": le.slug, "title": _lesson_title(le, lang), "lesson_type": le.lesson_type,
                         "duration": le.duration, "lab_slug": le.lab_slug, "completed": le.id in done,
                         "sequence_number": le.sequence_number}
                        for le in m.lessons if not le.deleted_at],
        })
    return out


def _lesson_title(le: Lesson, lang: str) -> str:
    tr = next((t for t in le.translations if t.language_code == lang), None)
    return tr.title if tr else le.title


@router.post("/courses/{key}/enroll")
def enroll(key: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    c = _course_or_404(db, key)
    if not db.scalar(select(Enrollment).where(Enrollment.user_id == user.id, Enrollment.course_id == c.id)):
        db.add(Enrollment(user_id=user.id, course_id=c.id))
        db.commit()
    return {"enrolled": True}


@router.get("/modules/{module_id}")
def get_module(module_id: uuid.UUID, lang: str = "uz", user: User = Depends(get_current_user),
               db: Session = Depends(get_db)) -> dict:
    m = db.get(Module, module_id)
    if not m or m.deleted_at:
        raise HTTPException(404, "Modul topilmadi")
    done = _completed_ids(db, user)
    return {"id": str(m.id), "course_id": str(m.course_id), "slug": m.slug, "title": m.title, "level": m.level,
            "description": m.description, "sequence_number": m.sequence_number, "translations": m.translations,
            "lessons": [{"id": str(le.id), "title": _lesson_title(le, lang), "lesson_type": le.lesson_type,
                         "completed": le.id in done, "sequence_number": le.sequence_number}
                        for le in m.lessons if not le.deleted_at]}


@router.get("/lessons/{lesson_id}")
def get_lesson(lesson_id: uuid.UUID, lang: str = "uz", user: User = Depends(get_current_user),
               db: Session = Depends(get_db)) -> dict:
    le = db.get(Lesson, lesson_id)
    if not le or le.deleted_at:
        raise HTTPException(404, "Dars topilmadi")
    tr = next((t for t in le.translations if t.language_code == lang), None)
    module = db.get(Module, le.module_id)
    siblings = [x for x in module.lessons if not x.deleted_at]
    idx = next(i for i, x in enumerate(siblings) if x.id == le.id)
    done = _completed_ids(db, user)
    return {
        "id": str(le.id), "module_id": str(le.module_id), "course_id": str(module.course_id),
        "module_title": module.title, "slug": le.slug, "lesson_type": le.lesson_type,
        "title": tr.title if tr else le.title, "content": tr.content if tr and tr.content else le.content,
        "video_url": le.video_url, "lab_slug": le.lab_slug, "duration": le.duration,
        "sequence_number": le.sequence_number, "completed": le.id in done,
        "prev_id": str(siblings[idx - 1].id) if idx > 0 else None,
        "next_id": str(siblings[idx + 1].id) if idx + 1 < len(siblings) else None,
        "translations": {t.language_code: {"title": t.title, "content": t.content} for t in le.translations},
        "original": {"title": le.title, "content": le.content},
    }


@router.post("/lessons/{lesson_id}/complete")
def complete_lesson(lesson_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    le = db.get(Lesson, lesson_id)
    if not le:
        raise HTTPException(404, "Dars topilmadi")
    if not db.scalar(select(LearningProgress).where(LearningProgress.user_id == user.id,
                                                    LearningProgress.lesson_id == lesson_id)):
        db.add(LearningProgress(user_id=user.id, lesson_id=lesson_id, completed_at=datetime.now(timezone.utc)))
        award_xp(db, user.id, 10)
        db.commit()
    module = db.get(Module, le.module_id)
    cert = maybe_issue_certificate(db, user.id, module.course_id)
    return {"completed": True, "certificate": cert}


# ------------------------------------------------------------------ tahrirlash (content:write)
class CourseIn(BaseModel):
    slug: str | None = None
    code: str | None = None
    title: str | None = None
    description: str | None = None
    difficulty: str | None = None
    status: str | None = None
    estimated_duration: int | None = None
    objectives: list[str] | None = None
    translations: dict | None = None
    category: str | None = None


class ModuleIn(BaseModel):
    course_id: uuid.UUID | None = None
    slug: str | None = None
    title: str | None = None
    level: str | None = None
    description: str | None = None
    sequence_number: int | None = None
    translations: dict | None = None


class LessonIn(BaseModel):
    module_id: uuid.UUID | None = None
    slug: str | None = None
    title: str | None = None
    lesson_type: str | None = None
    content: str | None = None
    video_url: str | None = None
    lab_slug: str | None = None
    duration: int | None = None
    sequence_number: int | None = None
    translations: dict[str, dict[str, str]] | None = None  # {"ru": {"title":..,"content":..}}


def _apply(obj, data: dict, skip: set[str] = frozenset()) -> None:
    for k, v in data.items():
        if k not in skip:
            setattr(obj, k, v)


@router.post("/courses", status_code=201)
def create_course(body: CourseIn, request: Request, user: User = Depends(require("content:write")),
                  db: Session = Depends(get_db)) -> dict:
    if not body.slug or not body.title:
        raise HTTPException(422, "slug va title majburiy")
    if db.scalar(select(Course).where(Course.slug == body.slug)):
        raise HTTPException(409, "Bu slug band")
    c = Course(organization_id=user.organization_id, status="draft")
    _apply(c, body.model_dump(exclude_none=True), {"category"})
    if body.category:
        cat = db.scalar(select(Category).where(Category.slug == body.category))
        c.category_id = cat.id if cat else None
    db.add(c)
    audit(db, user, "course.create", "course", body.slug, request)
    db.commit()
    return {"id": str(c.id), "slug": c.slug}


@router.put("/courses/{key}")
def update_course(key: str, body: CourseIn, request: Request, user: User = Depends(require("content:write")),
                  db: Session = Depends(get_db)) -> dict:
    c = _course_or_404(db, key)
    _apply(c, body.model_dump(exclude_none=True), {"category", "slug"})
    if body.category:
        cat = db.scalar(select(Category).where(Category.slug == body.category))
        c.category_id = cat.id if cat else c.category_id
    audit(db, user, "course.update", "course", str(c.id), request)
    db.commit()
    return {"id": str(c.id), "slug": c.slug}


@router.delete("/courses/{key}", status_code=204)
def delete_course(key: str, request: Request, user: User = Depends(require("content:write")),
                  db: Session = Depends(get_db)) -> None:
    c = _course_or_404(db, key)
    c.deleted_at = datetime.now(timezone.utc)
    audit(db, user, "course.delete", "course", str(c.id), request)
    db.commit()


@router.get("/courses/{key}/export", response_class=PlainTextResponse)
def export_course(key: str, _: User = Depends(require("content:write")), db: Session = Depends(get_db)) -> str:
    return export_pack(_course_or_404(db, key), db)


class PackIn(BaseModel):
    yaml: str
    replace: bool = True


@router.post("/courses/import", status_code=201)
def import_course(body: PackIn, request: Request, user: User = Depends(require("content:write")),
                  db: Session = Depends(get_db)) -> dict:
    try:
        data = yaml.safe_load(body.yaml)
        assert isinstance(data, dict) and "course" in data and "slug" in data["course"]
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"Paket formati noto'g'ri: {e}") from e
    c = import_pack(db, data, replace=body.replace, organization_id=user.organization_id)
    audit(db, user, "course.import", "course", c.slug, request)
    db.commit()
    return {"id": str(c.id), "slug": c.slug}


@router.post("/modules", status_code=201)
def create_module(body: ModuleIn, user: User = Depends(require("content:write")), db: Session = Depends(get_db)) -> dict:
    if not body.course_id or not body.title:
        raise HTTPException(422, "course_id va title majburiy")
    course = db.get(Course, body.course_id)
    if not course:
        raise HTTPException(404, "Kurs topilmadi")
    seq = body.sequence_number or (db.scalar(select(func.max(Module.sequence_number)).where(
        Module.course_id == course.id)) or 0) + 1
    m = Module(course_id=course.id, slug=body.slug or f"module-{seq}", title=body.title, level=body.level or "beginner",
               description=body.description or "", sequence_number=seq, translations=body.translations or {})
    db.add(m)
    audit(db, user, "module.create", "module", m.slug)
    db.commit()
    return {"id": str(m.id)}


@router.put("/modules/{module_id}")
def update_module(module_id: uuid.UUID, body: ModuleIn, user: User = Depends(require("content:write")),
                  db: Session = Depends(get_db)) -> dict:
    m = db.get(Module, module_id)
    if not m:
        raise HTTPException(404, "Modul topilmadi")
    _apply(m, body.model_dump(exclude_none=True), {"course_id"})
    audit(db, user, "module.update", "module", str(m.id))
    db.commit()
    return {"id": str(m.id)}


@router.delete("/modules/{module_id}", status_code=204)
def delete_module(module_id: uuid.UUID, user: User = Depends(require("content:write")), db: Session = Depends(get_db)) -> None:
    m = db.get(Module, module_id)
    if m:
        m.deleted_at = datetime.now(timezone.utc)
        audit(db, user, "module.delete", "module", str(m.id))
        db.commit()


@router.post("/lessons", status_code=201)
def create_lesson(body: LessonIn, user: User = Depends(require("content:write")), db: Session = Depends(get_db)) -> dict:
    if not body.module_id or not body.title:
        raise HTTPException(422, "module_id va title majburiy")
    if not db.get(Module, body.module_id):
        raise HTTPException(404, "Modul topilmadi")
    seq = body.sequence_number or (db.scalar(select(func.max(Lesson.sequence_number)).where(
        Lesson.module_id == body.module_id)) or 0) + 1
    le = Lesson(module_id=body.module_id, sequence_number=seq, slug=body.slug or f"lesson-{seq}", title=body.title)
    _apply(le, body.model_dump(exclude_none=True), {"translations", "module_id", "sequence_number", "slug", "title"})
    db.add(le)
    db.flush()
    _save_translations(db, le, body.translations)
    audit(db, user, "lesson.create", "lesson", str(le.id))
    db.commit()
    return {"id": str(le.id)}


@router.put("/lessons/{lesson_id}")
def update_lesson(lesson_id: uuid.UUID, body: LessonIn, user: User = Depends(require("content:write")),
                  db: Session = Depends(get_db)) -> dict:
    le = db.get(Lesson, lesson_id)
    if not le:
        raise HTTPException(404, "Dars topilmadi")
    _apply(le, body.model_dump(exclude_none=True), {"translations"})
    _save_translations(db, le, body.translations)
    audit(db, user, "lesson.update", "lesson", str(le.id))
    db.commit()
    return {"id": str(le.id)}


def _save_translations(db: Session, le: Lesson, trs: dict | None) -> None:
    for lang, tr in (trs or {}).items():
        if lang not in ("uz", "ru", "en"):
            continue
        row = next((t for t in le.translations if t.language_code == lang), None)
        if not (tr.get("title") or tr.get("content")):
            if row:
                db.delete(row)
            continue
        if not row:
            row = LessonTranslation(lesson_id=le.id, language_code=lang, title=tr.get("title") or le.title)
            le.translations.append(row)
        row.title = tr.get("title") or le.title
        row.content = tr.get("content", "")


@router.delete("/lessons/{lesson_id}", status_code=204)
def delete_lesson(lesson_id: uuid.UUID, user: User = Depends(require("content:write")), db: Session = Depends(get_db)) -> None:
    le = db.get(Lesson, lesson_id)
    if le:
        le.deleted_at = datetime.now(timezone.utc)
        audit(db, user, "lesson.delete", "lesson", str(le.id))
        db.commit()
