"""Boshlang'ich ma'lumotlar: rollar, ruxsatlar, admin, katalog, kontent paketlari, laboratoriyalar, CTF."""
from __future__ import annotations

import logging

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.rbac import PERMISSIONS, ROLES
from app.core.security import hash_flag, hash_password
from app.labengine.catalog import sync_catalog
from app.labengine.registry import sync_lab_dir
from app.models import (
    Category, Course, CtfChallenge, CtfEvent, InfrastructureHost, Organization, Permission, Role, RolePermission,
    User, UserRole,
)
from app.services.content import import_pack

log = logging.getLogger("clpe.seed")


def seed_rbac(db: Session) -> None:
    perms = {p.permission_key: p for p in db.scalars(select(Permission))}
    for key, desc in PERMISSIONS.items():
        if key not in perms:
            perms[key] = Permission(permission_key=key, description=desc)
            db.add(perms[key])
    db.flush()
    for name, (desc, keys) in ROLES.items():
        role = db.scalar(select(Role).where(Role.name == name))
        if not role:
            role = Role(name=name, description=desc)
            db.add(role)
            db.flush()
        have = {rp.permission.permission_key for rp in role.permissions}
        for k in keys:
            if k not in have:
                role.permissions.append(RolePermission(permission_id=perms[k].id, permission=perms[k]))
    db.commit()


def assign_role(db: Session, user: User, role_name: str) -> None:
    role = db.scalar(select(Role).where(Role.name == role_name))
    if role and not any(ur.role_id == role.id for ur in user.roles):
        user.roles.append(UserRole(role_id=role.id, role=role, organization_id=user.organization_id))


def seed_all(db: Session) -> None:
    s = get_settings()
    seed_rbac(db)
    org = db.scalar(select(Organization).where(Organization.name == "CLPE"))
    if not org:
        org = Organization(name="CLPE", type="platform")
        db.add(org)
        db.flush()
    if not db.scalar(select(User).where(User.email == s.seed_admin_email)):
        admin = User(username="admin", email=s.seed_admin_email, password_hash=hash_password(s.seed_admin_password),
                     full_name="Super Administrator", organization_id=org.id)
        db.add(admin)
        db.flush()
        assign_role(db, admin, "super_admin")
    if not db.scalar(select(InfrastructureHost)):
        db.add(InfrastructureHost(hostname="local", operating_system="linux", virtualization_provider=s.lab_provider))
    db.commit()

    sync_catalog(db)
    ok, errs = sync_lab_dir(db)
    log.info("Laboratoriyalar: %s yuklandi, %s xato", ok, len(errs))

    cat_data = yaml.safe_load((s.content_dir / "catalog.yaml").read_text(encoding="utf-8"))
    for c in cat_data.get("categories", []):
        if not db.scalar(select(Category).where(Category.slug == c["slug"])):
            db.add(Category(slug=c["slug"], title=c["title"], icon=c.get("icon", "shield")))
    db.commit()
    packs = {p.stem: p for p in (s.content_dir / "courses").glob("*.yaml")}
    for c in cat_data.get("courses", []):
        if db.scalar(select(Course).where(Course.slug == c["slug"])):
            continue
        if c["slug"] in packs:
            data = yaml.safe_load(packs[c["slug"]].read_text(encoding="utf-8"))
            data["course"].setdefault("code", c["code"])
            data["course"].setdefault("category", c["category"])
        else:
            data = {"course": {**c, "status": "draft"}, "modules": []}
        import_pack(db, data)

    ctf = yaml.safe_load((s.content_dir / "ctf.yaml").read_text(encoding="utf-8"))
    for ev in ctf.get("events", []):
        if db.scalar(select(CtfEvent).where(CtfEvent.slug == ev["slug"])):
            continue
        e = CtfEvent(slug=ev["slug"], title=ev["title"], description=ev.get("description", ""))
        db.add(e)
        db.flush()
        for ch in ev.get("challenges", []):
            db.add(CtfChallenge(event_id=e.id, title=ch["title"], description=ch.get("description", ""),
                                category=ch["category"], difficulty=ch.get("difficulty", "easy"),
                                points=ch.get("points", 100), flag_hash=hash_flag(ch["flag"]),
                                lab_slug=ch.get("lab_slug")))
    db.commit()
