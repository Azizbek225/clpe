"""Kontent paketlari: kurs + modullar + darslar + testlar YAML ko'rinishida import/eksport.
Har bir kurs (yo'nalish) mustaqil paket — alohida tahrirlanadi, almashtiriladi va ulashiladi."""
from __future__ import annotations

from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AnswerOption, Category, Course, Lesson, LessonTranslation, Module, Question, Quiz


def import_pack(db: Session, data: dict[str, Any], *, replace: bool = False, organization_id=None) -> Course:
    c = data["course"]
    course = db.scalar(select(Course).where(Course.slug == c["slug"]))
    if course and replace:
        for m in list(course.modules):
            db.delete(m)
        db.flush()
    if not course:
        course = Course(slug=c["slug"], title=c["title"], organization_id=organization_id)
        db.add(course)
    for f in ("title", "description", "difficulty", "estimated_duration", "objectives", "translations", "code"):
        if f in c:
            setattr(course, f, c[f])
    if c.get("category"):
        cat = db.scalar(select(Category).where(Category.slug == c["category"]))
        course.category_id = cat.id if cat else course.category_id
    course.status = c.get("status", "published")
    db.flush()
    if course.modules and not replace:
        db.commit()
        return course
    for mi, m in enumerate(data.get("modules", []), start=1):
        mod = Module(course_id=course.id, slug=m.get("slug", f"m{mi}"), title=m["title"], level=m.get("level", "beginner"),
                     description=m.get("description", ""), sequence_number=mi, translations=m.get("translations", {}))
        db.add(mod)
        db.flush()
        for li, le in enumerate(m.get("lessons", []), start=1):
            lesson = Lesson(module_id=mod.id, slug=le.get("slug", f"l{li}"), title=le["title"],
                            lesson_type=le.get("lesson_type", "lab" if le.get("lab") else "theory"),
                            content=le.get("content", ""), video_url=le.get("video_url"), lab_slug=le.get("lab"),
                            duration=le.get("duration", 10), sequence_number=li)
            db.add(lesson)
            db.flush()
            for lang, tr in (le.get("translations") or {}).items():
                db.add(LessonTranslation(lesson_id=lesson.id, language_code=lang, title=tr.get("title", le["title"]),
                                         content=tr.get("content", "")))
        if m.get("quiz"):
            q = m["quiz"]
            quiz = Quiz(module_id=mod.id, title=q["title"], passing_score=q.get("passing_score", 70))
            db.add(quiz)
            db.flush()
            for qq in q.get("questions", []):
                question = Question(quiz_id=quiz.id, question_text=qq["q"], question_type=qq.get("type", "single"),
                                    difficulty=qq.get("difficulty", m.get("level", "beginner")))
                db.add(question)
                db.flush()
                for oi, opt in enumerate(qq["options"]):
                    db.add(AnswerOption(question_id=question.id, answer_text=str(opt), is_correct=oi in qq["correct"]))
    db.commit()
    return course


def export_pack(course: Course, db: Session) -> str:
    cat = db.get(Category, course.category_id) if course.category_id else None
    out: dict[str, Any] = {"course": {
        "slug": course.slug, "code": course.code, "title": course.title, "description": course.description,
        "difficulty": course.difficulty, "estimated_duration": course.estimated_duration,
        "objectives": course.objectives, "translations": course.translations, "status": course.status,
        **({"category": cat.slug} if cat else {}),
    }, "modules": []}
    for m in course.modules:
        if m.deleted_at:
            continue
        md: dict[str, Any] = {"slug": m.slug, "title": m.title, "level": m.level, "description": m.description,
                              "translations": m.translations, "lessons": []}
        for le in m.lessons:
            if le.deleted_at:
                continue
            ld: dict[str, Any] = {"slug": le.slug, "title": le.title, "lesson_type": le.lesson_type,
                                  "duration": le.duration, "content": le.content}
            if le.lab_slug:
                ld["lab"] = le.lab_slug
            if le.video_url:
                ld["video_url"] = le.video_url
            if le.translations:
                ld["translations"] = {t.language_code: {"title": t.title, "content": t.content} for t in le.translations}
            md["lessons"].append(ld)
        quiz = db.scalar(select(Quiz).where(Quiz.module_id == m.id))
        if quiz:
            md["quiz"] = {"title": quiz.title, "passing_score": quiz.passing_score, "questions": [
                {"q": q.question_text, "type": q.question_type, "options": [o.answer_text for o in q.options],
                 "correct": [i for i, o in enumerate(q.options) if o.is_correct]} for q in quiz.questions]}
        out["modules"].append(md)
    return yaml.safe_dump(out, allow_unicode=True, sort_keys=False, width=120)
