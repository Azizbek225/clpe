"""VM shablonlari katalogi (catalog/machine_templates.yaml -> machine_templates jadvali)."""
from __future__ import annotations

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import MachineTemplate

FIELDS = ("name", "operating_system", "image_reference", "image_version", "image_checksum",
          "virtualization_provider", "role", "default_cpu", "default_ram", "meta")


def sync_catalog(db: Session) -> int:
    path = get_settings().catalog_file
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    count = 0
    for slug, spec in (data.get("templates") or {}).items():
        mt = db.scalar(select(MachineTemplate).where(MachineTemplate.slug == slug))
        if not mt:
            mt = MachineTemplate(slug=slug)
            db.add(mt)
        for f in FIELDS:
            if f in spec:
                setattr(mt, f, spec[f])
        count += 1
    db.commit()
    return count


def template_map(db: Session) -> dict[str, MachineTemplate]:
    return {t.slug: t for t in db.scalars(select(MachineTemplate))}
