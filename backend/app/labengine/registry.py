"""Laboratoriya manifestlarini DB bilan sinxronlash (labs/*.yaml va admin muharriri)."""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.labengine.catalog import template_map
from app.labengine.manifest import LabManifest, localize, parse_manifest, to_storage
from app.labengine.validators import validator_types
from app.models import LabTask, LabTemplate

log = logging.getLogger("clpe.labs")


def parse_for_db(db: Session, text: str) -> LabManifest:
    s = get_settings()
    return parse_manifest(text, known_templates=set(template_map(db)), allow_internet=s.allow_internet_labs,
                          validator_types=validator_types())


def upsert_lab(db: Session, text: str, *, organization_id=None, bump: bool = True) -> LabTemplate:
    m = parse_for_db(db, text)
    cfg = to_storage(m)
    lab = db.scalar(select(LabTemplate).where(LabTemplate.slug == m.id))
    if not lab:
        lab = LabTemplate(slug=m.id, version=m.version, organization_id=organization_id)
        db.add(lab)
    elif bump and lab.manifest_yaml != text:
        lab.version = max(lab.version + 1, m.version)
    lab.name = localize(m.title, "uz")
    lab.description = localize(m.description, "uz")
    lab.lab_type = m.lab_type
    lab.category = m.category
    lab.difficulty = m.difficulty
    lab.configuration_json = cfg
    lab.manifest_yaml = text
    lab.deleted_at = None
    db.flush()
    existing = {t.task_key: t for t in db.scalars(select(LabTask).where(LabTask.template_id == lab.id))}
    keep = set()
    for t in cfg["tasks"]:
        row = existing.get(t["id"]) or LabTask(template_id=lab.id, task_key=t["id"])
        row.title = localize(t["title"], "uz")
        row.description = localize(t["description"], "uz")
        row.validation_type = t["validation"]["type"]
        row.validation_configuration = t["validation"]["config"]
        row.max_score = t["points"]
        db.add(row)
        keep.add(t["id"])
    for key, row in existing.items():
        if key not in keep:
            db.delete(row)
    db.commit()
    return lab


def sync_lab_dir(db: Session) -> tuple[int, list[str]]:
    ok, errors = 0, []
    for path in sorted(get_settings().labs_dir.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        try:
            m = parse_for_db(db, text)
            existing = db.scalar(select(LabTemplate).where(LabTemplate.slug == m.id))
            # Admin paneldan tahrirlangan versiyani fayl qayta yozmasin
            if existing and existing.version > m.version:
                continue
            upsert_lab(db, text, bump=False)
            ok += 1
        except Exception as e:  # noqa: BLE001
            db.rollback()
            errors.append(f"{path.name}: {e}")
            log.warning("Lab manifest xatosi %s: %s", path.name, e)
    return ok, errors
