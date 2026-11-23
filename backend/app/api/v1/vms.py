"""VM API (7.4). Foydalanuvchi faqat o'z laboratoriyasidagi mashinalarni boshqaradi; labs:manage — barchasini."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import audit, get_current_user, require, user_permissions
from app.db import get_db
from app.labengine import orchestrator as orch
from app.labengine.providers.base import ProviderError
from app.models import LabInstance, LabMachine, LabSnapshot, User

router = APIRouter(prefix="/vms", tags=["vms"])


def _machine(db: Session, user: User, vm_id: uuid.UUID) -> tuple[LabMachine, LabInstance]:
    m = db.get(LabMachine, vm_id)
    if not m:
        raise HTTPException(404, "VM topilmadi")
    inst = db.get(LabInstance, m.lab_instance_id)
    if inst.user_id != user.id and "labs:manage" not in user_permissions(user):
        raise HTTPException(403, "Bu VM'ga ruxsat yo'q")
    if not m.vm_identifier:
        raise HTTPException(409, "VM hali yaratilmagan")
    return m, inst


@router.get("")
def list_vms(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    q = select(LabMachine, LabInstance).join(LabInstance).where(LabInstance.status.in_(orch.ACTIVE_STATUSES))
    if "labs:manage" not in user_permissions(user):
        q = q.where(LabInstance.user_id == user.id)
    return [{"id": str(m.id), "name": m.name, "role": m.role, "status": m.status, "os": m.operating_system,
             "lab": i.template.slug, "instance": i.instance_name, "provider": i.provider}
            for m, i in db.execute(q).all()]


@router.post("", status_code=405)
def create_vm() -> dict:
    # VM'lar faqat laboratoriya manifesti orqali yaratiladi (ixtiyoriy VM yaratish taqiqlangan — 9-bo'lim).
    raise HTTPException(405, "VM'lar laboratoriya orqali yaratiladi: POST /labs/{id}/start")


@router.post("/{vm_id}/start")
def start_vm(vm_id: uuid.UUID, user: User = Depends(require("labs:use")), db: Session = Depends(get_db)) -> dict:
    m, inst = _machine(db, user, vm_id)
    orch.provider_for(inst).start_vm(m.vm_identifier)
    m.status = "RUNNING"
    orch.event(db, inst, "vm_started", machine=m.name)
    audit(db, user, "vm.start", "lab_machine", str(m.id))
    db.commit()
    return {"status": m.status}


@router.post("/{vm_id}/shutdown")
def shutdown_vm(vm_id: uuid.UUID, user: User = Depends(require("labs:use")), db: Session = Depends(get_db)) -> dict:
    m, inst = _machine(db, user, vm_id)
    orch.provider_for(inst).stop_vm(m.vm_identifier)
    m.status = "STOPPED"
    orch.event(db, inst, "vm_stopped", machine=m.name)
    audit(db, user, "vm.shutdown", "lab_machine", str(m.id))
    db.commit()
    return {"status": m.status}


class SnapIn(BaseModel):
    name: str = Field("checkpoint", pattern=r"^[a-z0-9][a-z0-9-]{0,30}$")


@router.post("/{vm_id}/snapshot")
def snapshot_vm(vm_id: uuid.UUID, body: SnapIn, user: User = Depends(require("labs:use")),
                db: Session = Depends(get_db)) -> dict:
    m, inst = _machine(db, user, vm_id)
    try:
        sid = orch.provider_for(inst).create_snapshot(m.vm_identifier, body.name)
    except ProviderError as e:
        raise HTTPException(409, str(e)) from e
    db.add(LabSnapshot(lab_machine_id=m.id, snapshot_name=body.name, snapshot_identifier=sid))
    orch.event(db, inst, "snapshot", name=body.name, machines=[m.name])
    db.commit()
    return {"snapshot": body.name}


@router.get("/{vm_id}/metrics")
def metrics(vm_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    m, inst = _machine(db, user, vm_id)
    try:
        mt = orch.provider_for(inst).get_vm_metrics(m.vm_identifier)
    except ProviderError as e:
        raise HTTPException(409, str(e)) from e
    return {"cpu_percent": mt.cpu_percent, "ram_used_mb": mt.ram_used_mb, "ram_limit_mb": mt.ram_limit_mb}


@router.get("/{vm_id}/console")
def console(vm_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    m, inst = _machine(db, user, vm_id)
    provider = orch.provider_for(inst)
    if not provider.supports_console:
        raise HTTPException(409, f"{provider.name}: brauzer konsoli hozircha yo'q (VNC/noVNC rejada)")
    return {"websocket": f"/ws/console/{m.id}", "protocol": "raw-tty"}
