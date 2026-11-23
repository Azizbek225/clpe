"""Laboratoriya API (7.3) + skanerlash va topologiya grafigi."""
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import audit, get_current_user, require, user_permissions
from app.db import get_db
from app.labengine import orchestrator as orch
from app.labengine.catalog import template_map
from app.labengine.manifest import public_view
from app.labengine.providers.base import ProviderError
from app.labengine.scanner import SCAN_PROFILES, ScanError, build_topology
from app.labengine.tasks import dispatch
from app.labengine.validators import ValidationContext, get_validator
from app.models import LabEvent, LabInstance, LabScan, LabSubmission, LabTask, LabTemplate, User
from app.services.progress import award_xp

router = APIRouter(prefix="/labs", tags=["labs"])


def lab_or_404(db: Session, slug: str) -> LabTemplate:
    lab = db.scalar(select(LabTemplate).where(LabTemplate.slug == slug, LabTemplate.deleted_at.is_(None)))
    if not lab:
        raise HTTPException(404, "Laboratoriya topilmadi")
    return lab


def resolve_instance(db: Session, user: User, lab: LabTemplate, instance_id: uuid.UUID | None = None,
                     required: bool = True) -> LabInstance | None:
    if instance_id:
        inst = db.get(LabInstance, instance_id)
        if not inst or inst.template_id != lab.id:
            raise HTTPException(404, "Instansiya topilmadi")
        perms = user_permissions(user)
        if inst.user_id != user.id and not ({"labs:monitor", "labs:manage"} & perms):
            raise HTTPException(403, "Bu laboratoriyaga ruxsat yo'q")
        if inst.user_id != user.id and "labs:manage" not in perms and inst.organization_id != user.organization_id:
            raise HTTPException(403, "Boshqa tashkilot laboratoriyasi")
        return inst
    inst = db.scalar(select(LabInstance).where(LabInstance.user_id == user.id, LabInstance.template_id == lab.id)
                     .order_by(LabInstance.created_at.desc()))
    if not inst and required:
        raise HTTPException(404, "Bu laboratoriya hali ishga tushirilmagan")
    return inst


def instance_out(inst: LabInstance, db: Session) -> dict:
    subs = db.scalars(select(LabSubmission).where(LabSubmission.lab_instance_id == inst.id)).all()
    tasks = {t.id: t.task_key for t in db.scalars(select(LabTask).where(LabTask.template_id == inst.template_id))}
    best: dict[str, dict] = {}
    for s in sorted(subs, key=lambda s: s.created_at):
        key = tasks.get(s.task_id)
        if key and (key not in best or s.score >= best[key]["score"]):
            best[key] = {"score": s.score, "passed": s.passed, "feedback": s.feedback}
    return {
        "id": str(inst.id), "lab": inst.template.slug, "instance_name": inst.instance_name, "provider": inst.provider,
        "status": inst.status, "error": inst.error, "score": inst.score, "user_id": str(inst.user_id),
        "started_at": inst.started_at, "expires_at": inst.expires_at, "stopped_at": inst.stopped_at,
        "networks": [{"name": n.network_name, "cidr": n.cidr, "type": n.network_type, "policy": n.isolation_policy}
                     for n in inst.networks],
        "machines": [{"id": str(m.id), "name": m.name, "role": m.role, "status": m.status, "os": m.operating_system,
                      # nishon IP'lari "discovered" rejimida talabaga oshkor qilinmaydi
                      "ips": m.ip_addresses if (m.role == "attacker" or inst.template.configuration_json
                                                .get("topology", {}).get("reveal") == "full") else {},
                      "cpu": m.cpu_limit, "ram": m.ram_limit,
                      "snapshots": sorted({s.snapshot_name for s in m.snapshots})}
                     for m in inst.machines],
        "tasks": best,
    }


@router.get("")
def list_labs(lang: str = "uz", category: str | None = None, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)) -> list[dict]:
    q = select(LabTemplate).where(LabTemplate.deleted_at.is_(None), LabTemplate.status == "published")
    if category:
        q = q.where(LabTemplate.category == category)
    active = {i.template_id: i for i in db.scalars(select(LabInstance).where(
        LabInstance.user_id == user.id, LabInstance.status.in_(orch.ACTIVE_STATUSES)))}
    out = []
    for lab in db.scalars(q.order_by(LabTemplate.category, LabTemplate.slug)):
        v = public_view(lab.configuration_json, lang)
        inst = active.get(lab.id)
        out.append({k: v[k] for k in ("id", "title", "description", "category", "course", "lab_type", "difficulty",
                                      "duration_minutes")} | {
            "machines": len(lab.configuration_json["machines"]), "tasks": len(v["tasks"]), "points": v["scoring"]["maximum"],
            "version": lab.version, "active_instance": {"id": str(inst.id), "status": inst.status} if inst else None})
    return out


@router.get("/instances")
def list_instances(status: str | None = None, user: User = Depends(require("labs:monitor")),
                   db: Session = Depends(get_db)) -> list[dict]:
    """O'qituvchi/Lab Manager: talabalar laboratoriyalarini kuzatish."""
    q = select(LabInstance, User.username).join(User, User.id == LabInstance.user_id).order_by(
        LabInstance.created_at.desc()).limit(200)
    if "labs:manage" not in user_permissions(user):
        q = q.where(LabInstance.organization_id == user.organization_id)
    if status:
        q = q.where(LabInstance.status == status)
    return [{"id": str(i.id), "username": u, "lab": i.template.slug, "title": i.template.name, "status": i.status,
             "score": i.score, "provider": i.provider, "machines": len(i.machines), "started_at": i.started_at,
             "expires_at": i.expires_at} for i, u in db.execute(q).all()]


@router.get("/{slug}")
def get_lab(slug: str, lang: str = "uz", user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    lab = lab_or_404(db, slug)
    inst = resolve_instance(db, user, lab, required=False)
    return {**public_view(lab.configuration_json, lang), "version": lab.version,
            "scan_profiles": list(SCAN_PROFILES),
            "instance": instance_out(inst, db) if inst else None}


@router.post("/{slug}/start", status_code=202)
def start_lab(slug: str, request: Request, bg: BackgroundTasks, user: User = Depends(require("labs:use")),
              db: Session = Depends(get_db)) -> dict:
    lab = lab_or_404(db, slug)
    try:
        inst = orch.create_instance(db, user, lab)
    except orch.LabError as e:
        raise HTTPException(409, str(e)) from e
    if inst.status == "CREATED":
        dispatch("start", bg, inst.id)
    audit(db, user, "lab.start", "lab_instance", str(inst.id), request, slug)
    db.commit()
    return instance_out(inst, db)


@router.post("/{slug}/stop", status_code=202)
def stop_lab(slug: str, request: Request, bg: BackgroundTasks, instance_id: uuid.UUID | None = None,
             user: User = Depends(require("labs:use")), db: Session = Depends(get_db)) -> dict:
    inst = resolve_instance(db, user, lab_or_404(db, slug), instance_id)
    if inst.status in ("STOPPED", "STOPPING"):
        return instance_out(inst, db)
    dispatch("stop", bg, inst.id)
    audit(db, user, "lab.stop", "lab_instance", str(inst.id), request)
    db.commit()
    return instance_out(inst, db)


@router.post("/{slug}/reset", status_code=202)
def reset_lab(slug: str, bg: BackgroundTasks, instance_id: uuid.UUID | None = None,
              user: User = Depends(require("labs:use")), db: Session = Depends(get_db)) -> dict:
    inst = resolve_instance(db, user, lab_or_404(db, slug), instance_id)
    if inst.status != "RUNNING":
        raise HTTPException(409, "Faqat ishlayotgan laboratoriyani tiklash mumkin")
    dispatch("restore", bg, inst.id, "initial")
    audit(db, user, "lab.reset", "lab_instance", str(inst.id))
    db.commit()
    return instance_out(inst, db)


@router.get("/{slug}/status")
def lab_status(slug: str, instance_id: uuid.UUID | None = None, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)) -> dict:
    inst = resolve_instance(db, user, lab_or_404(db, slug), instance_id)
    return instance_out(inst, db)


@router.get("/{slug}/machines")
def lab_machines(slug: str, instance_id: uuid.UUID | None = None, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)) -> list[dict]:
    inst = resolve_instance(db, user, lab_or_404(db, slug), instance_id)
    provider = orch.provider_for(inst)
    out = []
    for m in instance_out(inst, db)["machines"]:
        row = next(x for x in inst.machines if x.name == m["name"])
        metrics = None
        if row.vm_identifier and row.status == "RUNNING":
            try:
                mt = provider.get_vm_metrics(row.vm_identifier)
                metrics = {"cpu_percent": mt.cpu_percent, "ram_used_mb": mt.ram_used_mb, "ram_limit_mb": mt.ram_limit_mb}
            except ProviderError:
                pass
        out.append({**m, "metrics": metrics,
                    "console": provider.supports_console and (m["role"] == "attacker")})
    return out


class SnapshotIn(BaseModel):
    name: str = Field("checkpoint", pattern=r"^[a-z0-9][a-z0-9-]{0,30}$")


@router.post("/{slug}/snapshot")
def snapshot(slug: str, body: SnapshotIn, instance_id: uuid.UUID | None = None,
             user: User = Depends(require("labs:use")), db: Session = Depends(get_db)) -> dict:
    inst = resolve_instance(db, user, lab_or_404(db, slug), instance_id)
    try:
        machines = orch.snapshot_instance(db, inst, body.name)
    except (orch.LabError, ProviderError) as e:
        raise HTTPException(409, str(e)) from e
    audit(db, user, "lab.snapshot", "lab_instance", str(inst.id), details=body.name)
    db.commit()
    return {"snapshot": body.name, "machines": machines}


@router.post("/{slug}/restore", status_code=202)
def restore(slug: str, body: SnapshotIn, bg: BackgroundTasks, instance_id: uuid.UUID | None = None,
            user: User = Depends(require("labs:use")), db: Session = Depends(get_db)) -> dict:
    inst = resolve_instance(db, user, lab_or_404(db, slug), instance_id)
    if inst.status != "RUNNING":
        raise HTTPException(409, "Laboratoriya ishlamayapti")
    dispatch("restore", bg, inst.id, body.name)
    audit(db, user, "lab.restore", "lab_instance", str(inst.id), details=body.name)
    db.commit()
    return {"restoring": body.name}


@router.get("/{slug}/events")
def events(slug: str, instance_id: uuid.UUID | None = None, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)) -> list[dict]:
    inst = resolve_instance(db, user, lab_or_404(db, slug), instance_id)
    rows = db.scalars(select(LabEvent).where(LabEvent.lab_instance_id == inst.id).order_by(LabEvent.created_at))
    return [{"id": str(e.id), "type": e.event_type, "details": e.event_details, "created_at": e.created_at} for e in rows]


class SubmitIn(BaseModel):
    task_id: str
    value: str | None = None
    ports: list[int] | None = None
    hosts: list[str] | None = None


@router.post("/{slug}/submit")
def submit(slug: str, body: SubmitIn, request: Request, user: User = Depends(require("labs:use")),
           db: Session = Depends(get_db)) -> dict:
    lab = lab_or_404(db, slug)
    inst = resolve_instance(db, user, lab)
    if inst.user_id != user.id:
        raise HTTPException(403, "Faqat o'z laboratoriyangiz uchun javob yuborasiz")
    if inst.status != "RUNNING":
        raise HTTPException(409, "Javob yuborish uchun laboratoriya ishlayotgan bo'lishi kerak")
    task = db.scalar(select(LabTask).where(LabTask.template_id == lab.id, LabTask.task_key == body.task_id))
    if not task:
        raise HTTPException(404, "Topshiriq topilmadi")
    cfg = dict(task.validation_configuration or {})
    if cfg.get("machine"):
        m = next((x for x in inst.machines if x.name == cfg["machine"]), None)
        tm = {t.id: t for t in template_map(db).values()}.get(m.machine_template_id) if m else None
        cfg["_template_meta"] = tm.meta if tm else {}
    scans = [s.hosts for s in db.scalars(select(LabScan).where(LabScan.lab_instance_id == inst.id)
                                         .order_by(LabScan.created_at))]
    ctx = ValidationContext(config=cfg, max_score=task.max_score, submitted=body.model_dump(exclude_none=True),
                            instance=inst, scans=scans, provider=orch.provider_for(inst))
    try:
        res = get_validator(task.validation_type)(ctx)
    except KeyError as e:
        raise HTTPException(500, f"Validator topilmadi: {task.validation_type}") from e
    prev_best = max([s.score for s in db.scalars(select(LabSubmission).where(
        LabSubmission.lab_instance_id == inst.id, LabSubmission.task_id == task.id))], default=0)
    db.add(LabSubmission(user_id=user.id, lab_instance_id=inst.id, task_id=task.id,
                         submitted_data=body.model_dump(exclude_none=True), score=res.score, passed=res.passed,
                         feedback=res.feedback))
    if res.score > prev_best:
        inst.score += res.score - prev_best
        if res.passed:
            award_xp(db, user.id, max(5, res.score))
    orch.event(db, inst, "task_submitted", task=task.task_key, passed=res.passed, score=res.score)
    audit(db, user, "lab.submit", "lab_task", task.task_key, request)
    db.commit()
    return {"task_id": task.task_key, "passed": res.passed, "score": res.score, "max_score": task.max_score,
            "feedback": res.feedback, "pending": res.pending, "total_score": inst.score}


class ScanIn(BaseModel):
    target: str = Field(..., max_length=43)
    profile: str = "quick"


@router.post("/{slug}/scan")
def scan(slug: str, body: ScanIn, request: Request, user: User = Depends(require("labs:use")),
         db: Session = Depends(get_db)) -> dict:
    """Hujumchi mashina ICHIDA nmap ishga tushiriladi va natija grafikka qo'shiladi."""
    lab = lab_or_404(db, slug)
    inst = resolve_instance(db, user, lab)
    try:
        s = orch.run_scan(db, inst, user.id, body.target, body.profile)
    except (ScanError, orch.LabError, ProviderError) as e:
        raise HTTPException(422, str(e)) from e
    audit(db, user, "lab.scan", "lab_instance", str(inst.id), request, f"{body.profile} {s.target}")
    db.commit()
    return {"scan_id": str(s.id), "hosts": s.hosts, "topology": _topology(db, inst)}


class ImportIn(BaseModel):
    xml: str = Field(..., max_length=5_000_000)


@router.post("/{slug}/scan/import")
def scan_import(slug: str, body: ImportIn, user: User = Depends(require("labs:use")),
                db: Session = Depends(get_db)) -> dict:
    """Talaba terminalda olgan `nmap -oX` natijasini yuklaydi."""
    inst = resolve_instance(db, user, lab_or_404(db, slug))
    try:
        s = orch.import_scan(db, inst, user.id, body.xml)
    except ScanError as e:
        raise HTTPException(422, str(e)) from e
    return {"scan_id": str(s.id), "hosts": s.hosts, "topology": _topology(db, inst)}


@router.get("/{slug}/scans")
def scans(slug: str, instance_id: uuid.UUID | None = None, user: User = Depends(get_current_user),
          db: Session = Depends(get_db)) -> list[dict]:
    inst = resolve_instance(db, user, lab_or_404(db, slug), instance_id)
    return [{"id": str(s.id), "source": s.source, "target": s.target, "profile": s.profile, "hosts": s.hosts,
             "created_at": s.created_at}
            for s in db.scalars(select(LabScan).where(LabScan.lab_instance_id == inst.id).order_by(LabScan.created_at))]


@router.get("/{slug}/topology")
def topology(slug: str, instance_id: uuid.UUID | None = None, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)) -> dict:
    inst = resolve_instance(db, user, lab_or_404(db, slug), instance_id)
    return _topology(db, inst, full=inst.user_id != user.id)


def _topology(db: Session, inst: LabInstance, full: bool = False) -> dict:
    scans = [s.hosts for s in db.scalars(select(LabScan).where(LabScan.lab_instance_id == inst.id)
                                         .order_by(LabScan.created_at))]
    reveal = "full" if full else inst.template.configuration_json.get("topology", {}).get("reveal", "discovered")
    return build_topology(inst, scans, reveal)
