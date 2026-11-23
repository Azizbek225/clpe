"""WebSocket: laboratoriya holati real vaqtda (7.7) va brauzer terminali."""
import asyncio
import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.deps import get_user_from_token, user_permissions
from app.db import SessionLocal
from app.labengine import orchestrator as orch
from app.models import LabEvent, LabInstance, LabMachine, LabTemplate, MachineTemplate

router = APIRouter()


@router.websocket("/ws/labs/{lab_id}")
async def lab_stream(ws: WebSocket, lab_id: str, token: str | None = None):
    """lab_id — laboratoriya slug'i yoki instansiya UUID'si. Har 2 soniyada holat, yangi hodisalar va metrikalar."""
    db = SessionLocal()
    try:
        user = get_user_from_token(db, token)
        if not user:
            await ws.close(code=4401)
            return
        inst = _find_instance(db, user, lab_id)
        if not inst:
            await ws.close(code=4404)
            return
        await ws.accept()
        last_seen = None
        while True:
            db.expire_all()
            inst = db.get(LabInstance, inst.id)
            q = select(LabEvent).where(LabEvent.lab_instance_id == inst.id).order_by(LabEvent.created_at)
            if last_seen:
                q = q.where(LabEvent.created_at > last_seen)
            evs = db.scalars(q).all()
            if evs:
                last_seen = evs[-1].created_at
            metrics = {}
            if inst.status == "RUNNING":
                provider = orch.provider_for(inst)
                for m in inst.machines:
                    try:
                        mt = await asyncio.to_thread(provider.get_vm_metrics, m.vm_identifier)
                        metrics[m.name] = {"cpu": mt.cpu_percent, "ram": mt.ram_used_mb, "ram_limit": mt.ram_limit_mb}
                    except Exception:  # noqa: BLE001
                        pass
            await ws.send_text(json.dumps({
                "status": inst.status, "score": inst.score, "error": inst.error,
                "machines": {m.name: m.status for m in inst.machines}, "metrics": metrics,
                "events": [{"type": e.event_type, "details": e.event_details, "created_at": e.created_at.isoformat()}
                           for e in evs],
            }, default=str))
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    finally:
        db.close()


def _find_instance(db, user, lab_id: str):
    try:
        inst = db.get(LabInstance, uuid.UUID(lab_id))
        if inst and (inst.user_id == user.id or {"labs:monitor", "labs:manage"} & user_permissions(user)):
            return inst
        return None
    except ValueError:
        lab = db.scalar(select(LabTemplate).where(LabTemplate.slug == lab_id))
        if not lab:
            return None
        return db.scalar(select(LabInstance).where(LabInstance.user_id == user.id, LabInstance.template_id == lab.id)
                         .order_by(LabInstance.created_at.desc()))


@router.websocket("/ws/console/{machine_id}")
async def console(ws: WebSocket, machine_id: uuid.UUID, token: str | None = None):
    """Lab mashinasi ICHIDAGI shell (Docker exec). Host tizimiga hech qanday kirish yo'q.
    Faqat manifestda konsol ruxsat etilgan mashinalar (default: attacker roli)."""
    db = SessionLocal()
    try:
        user = get_user_from_token(db, token)
        m = db.get(LabMachine, machine_id)
        inst = db.get(LabInstance, m.lab_instance_id) if m else None
        if not user or not inst or inst.user_id != user.id or inst.status != "RUNNING":
            await ws.close(code=4403)
            return
        spec = next((x for x in inst.template.configuration_json["machines"] if x["name"] == m.name), {})
        allowed = spec.get("console") if spec.get("console") is not None else m.role == "attacker"
        provider = orch.provider_for(inst)
        if not allowed or not provider.supports_console:
            await ws.close(code=4403)
            return
        vm_id = m.vm_identifier
        tmpl = db.get(MachineTemplate, m.machine_template_id) if m.machine_template_id else None
        shell = (tmpl.meta or {}).get("shell", "/bin/sh") if tmpl else "/bin/sh"
        if shell not in ("/bin/sh", "/bin/bash", "/bin/zsh"):
            shell = "/bin/sh"
    finally:
        db.close()

    await ws.accept()
    exec_id, sock = await asyncio.to_thread(provider.open_console, vm_id, shell)
    sock.setblocking(True)

    async def pump_out():
        while True:
            data = await asyncio.to_thread(sock.recv, 4096)
            if not data:
                break
            await ws.send_bytes(data)

    reader = asyncio.create_task(pump_out())
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if msg.get("text"):
                try:
                    ctl = json.loads(msg["text"])
                except json.JSONDecodeError:
                    ctl = None
                if isinstance(ctl, dict) and ctl.get("type") == "resize":
                    await asyncio.to_thread(provider.resize_console, exec_id, int(ctl["rows"]), int(ctl["cols"]))
                    continue
                if isinstance(ctl, dict) and ctl.get("type") == "input":
                    await asyncio.to_thread(sock.sendall, str(ctl.get("data", "")).encode())
                    continue
                await asyncio.to_thread(sock.sendall, msg["text"].encode())
            elif msg.get("bytes"):
                await asyncio.to_thread(sock.sendall, msg["bytes"])
    except WebSocketDisconnect:
        pass
    finally:
        reader.cancel()
        try:
            sock.close()
        except OSError:
            pass
