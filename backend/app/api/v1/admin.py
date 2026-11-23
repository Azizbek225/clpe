"""Administrator paneli API (15-bo'lim)."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.deps import audit, require, user_role_names
from app.core.rbac import ROLES
from app.core.security import hash_password
from app.db import get_db
from app.labengine import orchestrator as orch
from app.labengine.catalog import template_map
from app.labengine.manifest import ManifestError
from app.labengine.providers import available_providers, get_provider
from app.labengine.registry import parse_for_db, upsert_lab
from app.labengine.validators import validator_types
from app.models import (
    AuditLog, Course, InfrastructureHost, LabEvent, LabInstance, LabMachine, LabTemplate, MachineTemplate,
    Organization, Role, User, UserRole,
)
from app.services.seed import assign_role

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard")
def dashboard(_: User = Depends(require("reports:read")), db: Session = Depends(get_db)) -> dict:
    day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    running = db.scalars(select(LabInstance).where(LabInstance.status == "RUNNING")).all()
    vms = [m for i in running for m in i.machines if m.status == "RUNNING"]
    hosts = db.scalars(select(InfrastructureHost)).all()
    cap_cpu = sum(h.total_cpu for h in hosts) or 1
    cap_ram = sum(h.total_ram for h in hosts) or 1
    by_status = dict(db.execute(select(LabInstance.status, func.count()).group_by(LabInstance.status)).all())
    return {
        "users_total": db.scalar(select(func.count()).select_from(User)),
        "users_active_24h": db.scalar(select(func.count(func.distinct(AuditLog.user_id))).where(
            AuditLog.created_at >= day_ago)),
        "courses": db.scalar(select(func.count()).select_from(Course).where(Course.deleted_at.is_(None))),
        "labs_templates": db.scalar(select(func.count()).select_from(LabTemplate).where(LabTemplate.deleted_at.is_(None))),
        "labs_active": len(running), "vms_running": len(vms), "labs_by_status": by_status,
        "cpu_allocated_pct": round(100 * sum(m.cpu_limit for m in vms) / cap_cpu, 1),
        "ram_allocated_pct": round(100 * sum(m.ram_limit for m in vms) / cap_ram, 1),
        "lab_errors_24h": db.scalar(select(func.count()).select_from(LabInstance).where(
            LabInstance.status == "ERROR", LabInstance.updated_at >= day_ago)),
        "security_events_24h": db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "auth.login_failed", AuditLog.created_at >= day_ago)),
        "provider": get_settings().lab_provider,
    }


# ------------------------------------------------------------------ foydalanuvchilar
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = ""
    roles: list[str] = ["student"]
    organization_id: uuid.UUID | None = None


class UserUpdate(BaseModel):
    roles: list[str] | None = None
    status: str | None = Field(None, pattern="^(active|blocked)$")
    organization_id: uuid.UUID | None = None


def _user_row(u: User) -> dict:
    return {"id": str(u.id), "username": u.username, "email": u.email, "full_name": u.full_name, "status": u.status,
            "xp": u.xp, "roles": user_role_names(u), "organization_id": str(u.organization_id) if u.organization_id else None,
            "created_at": u.created_at}


@router.get("/users")
def users(q: str | None = None, _: User = Depends(require("users:manage")), db: Session = Depends(get_db)) -> list[dict]:
    stmt = select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc()).limit(500)
    if q:
        stmt = stmt.where(User.username.ilike(f"%{q}%") | User.email.ilike(f"%{q}%"))
    return [_user_row(u) for u in db.scalars(stmt)]


@router.get("/roles")
def roles(_: User = Depends(require("users:manage")), db: Session = Depends(get_db)) -> list[dict]:
    return [{"name": r.name, "description": r.description,
             "permissions": sorted(rp.permission.permission_key for rp in r.permissions)} for r in db.scalars(select(Role))]


@router.post("/users", status_code=201)
def create_user(body: UserCreate, request: Request, admin: User = Depends(require("users:manage")),
                db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(User).where((User.email == body.email.lower()) | (User.username == body.username))):
        raise HTTPException(409, "Foydalanuvchi mavjud")
    u = User(username=body.username, email=body.email.lower(), password_hash=hash_password(body.password),
             full_name=body.full_name, organization_id=body.organization_id or admin.organization_id)
    db.add(u)
    db.flush()
    _set_roles(db, admin, u, body.roles)
    audit(db, admin, "user.create", "user", str(u.id), request)
    db.commit()
    return _user_row(u)


def _set_roles(db: Session, admin: User, u: User, names: list[str]) -> None:
    for n in names:
        if n not in ROLES:
            raise HTTPException(422, f"Noma'lum rol: {n}")
        if n == "super_admin" and "super_admin" not in user_role_names(admin):
            raise HTTPException(403, "Super admin rolini faqat super admin beradi")
    u.roles.clear()
    db.flush()
    for n in names:
        assign_role(db, u, n)


@router.put("/users/{user_id}")
def update_user(user_id: uuid.UUID, body: UserUpdate, request: Request, admin: User = Depends(require("users:manage")),
                db: Session = Depends(get_db)) -> dict:
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    if body.roles is not None:
        _set_roles(db, admin, u, body.roles)
    if body.status:
        u.status = body.status
    if body.organization_id:
        u.organization_id = body.organization_id
        for ur in u.roles:
            ur.organization_id = body.organization_id
    audit(db, admin, "user.update", "user", str(u.id), request, body.model_dump_json(exclude_none=True))
    db.commit()
    return _user_row(u)


# ------------------------------------------------------------------ tashkilotlar
class OrgIn(BaseModel):
    name: str
    type: str = "university"
    address: str | None = None


@router.get("/organizations")
def orgs(_: User = Depends(require("org:manage")), db: Session = Depends(get_db)) -> list[dict]:
    counts = dict(db.execute(select(User.organization_id, func.count()).group_by(User.organization_id)).all())
    return [{"id": str(o.id), "name": o.name, "type": o.type, "address": o.address, "users": counts.get(o.id, 0)}
            for o in db.scalars(select(Organization).where(Organization.deleted_at.is_(None)))]


@router.post("/organizations", status_code=201)
def create_org(body: OrgIn, admin: User = Depends(require("system:manage")), db: Session = Depends(get_db)) -> dict:
    o = Organization(**body.model_dump())
    db.add(o)
    audit(db, admin, "org.create", "organization", body.name)
    db.commit()
    return {"id": str(o.id)}


# ------------------------------------------------------------------ laboratoriya manifestlari
class ManifestIn(BaseModel):
    yaml: str = Field(..., max_length=200_000)


@router.get("/labs")
def admin_labs(_: User = Depends(require("labs:author")), db: Session = Depends(get_db)) -> list[dict]:
    return [{"slug": x.slug, "name": x.name, "category": x.category, "difficulty": x.difficulty, "lab_type": x.lab_type,
             "version": x.version, "status": x.status, "updated_at": x.updated_at,
             "machines": len(x.configuration_json.get("machines", [])), "tasks": len(x.configuration_json.get("tasks", []))}
            for x in db.scalars(select(LabTemplate).where(LabTemplate.deleted_at.is_(None)).order_by(LabTemplate.slug))]


@router.get("/labs/{slug}/manifest", response_class=PlainTextResponse)
def get_manifest(slug: str, _: User = Depends(require("labs:author")), db: Session = Depends(get_db)) -> str:
    lab = db.scalar(select(LabTemplate).where(LabTemplate.slug == slug))
    if not lab:
        raise HTTPException(404, "Laboratoriya topilmadi")
    return lab.manifest_yaml


@router.post("/labs/validate")
def validate_manifest(body: ManifestIn, _: User = Depends(require("labs:author")), db: Session = Depends(get_db)) -> dict:
    try:
        m = parse_for_db(db, body.yaml)
    except ManifestError as e:
        return {"valid": False, "errors": e.errors}
    return {"valid": True, "errors": [], "id": m.id, "machines": [x.name for x in m.machines],
            "networks": [n.name for n in m.networks], "tasks": [t.id for t in m.tasks]}


@router.post("/labs", status_code=201)
def save_manifest(body: ManifestIn, request: Request, user: User = Depends(require("labs:author")),
                  db: Session = Depends(get_db)) -> dict:
    """Yangi laboratoriya qo'shish yoki mavjudini yangilash — kod o'zgartirmasdan (10-bo'lim)."""
    try:
        lab = upsert_lab(db, body.yaml, organization_id=user.organization_id)
    except ManifestError as e:
        raise HTTPException(422, {"errors": e.errors}) from e
    audit(db, user, "lab_template.save", "lab_template", lab.slug, request, f"v{lab.version}")
    db.commit()
    return {"slug": lab.slug, "version": lab.version}


@router.post("/labs/{slug}/status")
def set_lab_status(slug: str, status: str, user: User = Depends(require("labs:author")), db: Session = Depends(get_db)) -> dict:
    if status not in ("published", "draft", "archived"):
        raise HTTPException(422, "status: published|draft|archived")
    lab = db.scalar(select(LabTemplate).where(LabTemplate.slug == slug))
    if not lab:
        raise HTTPException(404, "Laboratoriya topilmadi")
    lab.status = status
    audit(db, user, "lab_template.status", "lab_template", slug, details=status)
    db.commit()
    return {"slug": slug, "status": status}


@router.delete("/labs/{slug}", status_code=204)
def delete_lab(slug: str, user: User = Depends(require("labs:author")), db: Session = Depends(get_db)) -> None:
    lab = db.scalar(select(LabTemplate).where(LabTemplate.slug == slug))
    if lab:
        lab.deleted_at = datetime.now(timezone.utc)
        audit(db, user, "lab_template.delete", "lab_template", slug)
        db.commit()


@router.get("/lab-engine")
def lab_engine_info(_: User = Depends(require("labs:author")), db: Session = Depends(get_db)) -> dict:
    s = get_settings()
    try:
        health = get_provider(s.lab_provider).healthcheck()
    except Exception as e:  # noqa: BLE001
        health = {"provider": s.lab_provider, "ok": False, "error": str(e)}
    return {"active_provider": s.lab_provider, "providers": available_providers(), "health": health,
            "validator_types": sorted(validator_types()), "allow_internet_labs": s.allow_internet_labs,
            "templates": [{"slug": t.slug, "name": t.name, "os": t.operating_system, "provider": t.virtualization_provider,
                           "role": t.role, "image": t.image_reference, "checksum": t.image_checksum,
                           "cpu": t.default_cpu, "ram": t.default_ram} for t in template_map(db).values()]}


class TemplateIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    name: str
    operating_system: str
    image_reference: str
    image_version: str = "latest"
    image_checksum: str | None = None
    virtualization_provider: str
    role: str = "target"
    default_cpu: float = 1.0
    default_ram: int = 512
    meta: dict = {}


@router.post("/machine-templates", status_code=201)
def upsert_template(body: TemplateIn, user: User = Depends(require("templates:manage")),
                    db: Session = Depends(get_db)) -> dict:
    if body.virtualization_provider not in available_providers():
        raise HTTPException(422, "Noma'lum provayder")
    t = db.scalar(select(MachineTemplate).where(MachineTemplate.slug == body.slug)) or MachineTemplate(slug=body.slug)
    for k, v in body.model_dump().items():
        setattr(t, k, v)
    db.add(t)
    audit(db, user, "machine_template.save", "machine_template", body.slug)
    db.commit()
    return {"slug": t.slug}


@router.get("/hosts")
def hosts(_: User = Depends(require("templates:manage")), db: Session = Depends(get_db)) -> list[dict]:
    return [{"id": str(h.id), "hostname": h.hostname, "os": h.operating_system, "provider": h.virtualization_provider,
             "cpu": h.total_cpu, "ram": h.total_ram, "status": h.available_status}
            for h in db.scalars(select(InfrastructureHost))]


@router.post("/instances/{instance_id}/stop", status_code=202)
def force_stop(instance_id: uuid.UUID, user: User = Depends(require("labs:manage")), db: Session = Depends(get_db)) -> dict:
    inst = db.get(LabInstance, instance_id)
    if not inst:
        raise HTTPException(404)
    audit(db, user, "lab.force_stop", "lab_instance", str(inst.id))
    db.commit()
    orch.stop_instance(inst.id, reason="admin")
    return {"stopped": True}


@router.get("/audit")
def audit_logs(limit: int = 200, action: str | None = None, _: User = Depends(require("audit:read")),
               db: Session = Depends(get_db)) -> list[dict]:
    q = select(AuditLog, User.username).outerjoin(User, User.id == AuditLog.user_id).order_by(
        AuditLog.created_at.desc()).limit(min(limit, 1000))
    if action:
        q = q.where(AuditLog.action.ilike(f"{action}%"))
    return [{"id": str(a.id), "username": u, "action": a.action, "resource_type": a.resource_type,
             "resource_id": a.resource_id, "ip": a.ip_address, "details": a.details, "created_at": a.created_at}
            for a, u in db.execute(q).all()]


@router.get("/lab-errors")
def lab_errors(_: User = Depends(require("labs:monitor")), db: Session = Depends(get_db)) -> list[dict]:
    q = select(LabEvent).where(LabEvent.event_type.in_(("warning",))).order_by(LabEvent.created_at.desc()).limit(100)
    errs = [{"instance": str(e.lab_instance_id), "details": e.event_details, "created_at": e.created_at}
            for e in db.scalars(q)]
    failed = [{"instance": str(i.id), "details": {"error": i.error}, "created_at": i.updated_at}
              for i in db.scalars(select(LabInstance).where(LabInstance.status == "ERROR").limit(100))]
    return failed + errs


_ = LabMachine, UserRole  # re-export guard
