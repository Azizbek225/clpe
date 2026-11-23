"""Lab orkestratori: 8.2-bo'limdagi ishga tushirish oqimi, rollback, reset, snapshot, tozalash.

Har bir funksiya o'z DB sessiyasini ochadi — Celery worker'da yoki fon oqimida ishlay oladi.
"""
from __future__ import annotations

import ipaddress
import logging
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.labengine.catalog import template_map
from app.labengine.providers import get_provider
from app.labengine.providers.base import NetworkConfig, ProviderError, VirtualizationProvider, VMConfig
from app.labengine.scanner import build_nmap_argv, parse_nmap_xml, validate_target
from app.models import AuditLog, LabEvent, LabInstance, LabMachine, LabNetwork, LabScan, LabSnapshot, LabTemplate

log = logging.getLogger("clpe.orchestrator")

ACTIVE_STATUSES = ("QUEUED", "CREATED", "PREPARING", "STARTING", "RUNNING", "PAUSED", "RESETTING")
VM_STATUSES = ("CREATED", "PREPARING", "STARTING", "RUNNING", "PAUSED", "STOPPING", "STOPPED", "RESETTING",
               "ERROR", "DELETING")


class LabError(RuntimeError):
    pass


def now() -> datetime:
    return datetime.now(timezone.utc)


def provider_for(instance: LabInstance) -> VirtualizationProvider:
    return get_provider(instance.provider)


def event(db: Session, inst: LabInstance, etype: str, **details) -> None:
    db.add(LabEvent(lab_instance_id=inst.id, event_type=etype, event_details=details))


def set_status(db: Session, inst: LabInstance, status: str, **details) -> None:
    old = inst.status
    inst.status = status
    event(db, inst, "status", old=old, new=status, **details)
    db.add(AuditLog(user_id=inst.user_id, organization_id=inst.organization_id, action=f"lab.status.{status.lower()}",
                    resource_type="lab_instance", resource_id=str(inst.id), details=f"{old}->{status}"))
    db.commit()


# ------------------------------------------------------------------ IPAM
def allocate_subnets(db: Session, count: int, provider_name: str | None = None) -> list[str]:
    pool = ipaddress.ip_network(get_settings().lab_subnet_pool)
    used = set(db.scalars(
        select(LabNetwork.cidr).join(LabInstance).where(LabInstance.status.in_(ACTIVE_STATUSES + ("STOPPING",)))))
    host_used = []
    if provider_name:
        try:
            host_used = [ipaddress.ip_network(c) for c in get_provider(provider_name).used_cidrs()]
        except Exception:  # noqa: BLE001
            log.warning("Provayderdan band subnetlarni olib bo'lmadi")
    out: list[str] = []
    for sub in pool.subnets(new_prefix=24):
        s = str(sub)
        if any(sub.overlaps(h) for h in host_used):
            continue
        if s not in used and s not in out:
            out.append(s)
            if len(out) == count:
                return out
    raise LabError("Bo'sh tarmoq manzillari qolmadi")


# ------------------------------------------------------------------ yaratish
def create_instance(db: Session, user, lab: LabTemplate) -> LabInstance:
    """Talaba laboratoriyani tanladi: DB yozuvlarini tayyorlaydi (resurslar keyin fon jarayonida)."""
    s = get_settings()
    active = db.scalars(select(LabInstance).where(LabInstance.user_id == user.id,
                                                  LabInstance.status.in_(ACTIVE_STATUSES))).all()
    for a in active:
        if a.template_id == lab.id:
            return a
    if len(active) >= s.max_active_labs_per_user:
        raise LabError(f"Bir vaqtda {s.max_active_labs_per_user} tadan ortiq laboratoriya ishlatib bo'lmaydi")
    cfg = lab.configuration_json
    templates = template_map(db)
    provider_name = s.lab_provider
    if provider_name != "mock":
        kinds = {templates[m["template"]].virtualization_provider for m in cfg["machines"]}
        if len(kinds) != 1:
            raise LabError("MVP: bitta laboratoriyadagi barcha mashinalar bitta provayderda bo'lishi kerak")
        provider_name = kinds.pop()
    inst = LabInstance(
        user_id=user.id, organization_id=user.organization_id, template_id=lab.id, provider=provider_name,
        instance_name=f"clpe-{secrets.token_hex(4)}", status="CREATED",
    )
    db.add(inst)
    db.flush()
    cidrs = allocate_subnets(db, len(cfg["networks"]), provider_name)
    net_by_name = {}
    for spec, cidr in zip(cfg["networks"], cidrs):
        policy = "malware-strict" if cfg["lab_type"] == "malware" else ("internet" if spec["internet"] else "no-internet")
        n = LabNetwork(lab_instance_id=inst.id, network_name=spec["name"], network_type=spec["type"], cidr=cidr,
                       isolation_policy=policy)
        db.add(n)
        net_by_name[spec["name"]] = n
    counters = {name: 10 for name in net_by_name}
    for spec in cfg["machines"]:
        t = templates[spec["template"]]
        ips = {}
        for net_name in spec["networks"]:
            hosts = list(ipaddress.ip_network(net_by_name[net_name].cidr).hosts())
            if spec["role"] == "attacker":
                ips[net_name] = str(hosts[4])  # .5
            else:
                ips[net_name] = str(hosts[counters[net_name] - 1])
                counters[net_name] += 1
        db.add(LabMachine(
            lab_instance_id=inst.id, machine_template_id=t.id, name=spec["name"], role=spec["role"],
            operating_system=t.operating_system, ip_addresses=ips,
            cpu_limit=spec.get("cpu") or t.default_cpu, ram_limit=spec.get("ram") or t.default_ram,
        ))
    event(db, inst, "created", lab=lab.slug)
    db.commit()
    db.refresh(inst)
    return inst


def _capacity_ok(db: Session, inst: LabInstance) -> bool:
    s = get_settings()
    if s.lab_provider == "mock":
        return True
    from app.models import InfrastructureHost
    hosts = db.scalars(select(InfrastructureHost).where(InfrastructureHost.available_status == "online")).all()
    if not hosts:
        return True
    cap_ram = sum(h.total_ram for h in hosts)
    used = db.scalars(select(LabMachine.ram_limit).join(LabInstance).where(
        LabInstance.status.in_(("PREPARING", "STARTING", "RUNNING", "RESETTING")))).all()
    need = sum(m.ram_limit for m in inst.machines)
    return sum(used) + need <= cap_ram


# ------------------------------------------------------------------ ishga tushirish (8.2)
def start_instance(instance_id) -> None:
    db = SessionLocal()
    try:
        inst = db.get(LabInstance, instance_id)
        if not inst or inst.status not in ("CREATED", "QUEUED"):
            return
        if not _capacity_ok(db, inst):
            set_status(db, inst, "QUEUED", reason="Resurslar band — navbatga qo'yildi")
            return
        _run_start(db, inst)
    finally:
        db.close()


def _run_start(db: Session, inst: LabInstance) -> None:
    provider = provider_for(inst)
    templates = {t.id: t for t in template_map(db).values()}
    cfg = inst.template.configuration_json
    rollback: list[Callable[[], None]] = []
    try:
        set_status(db, inst, "PREPARING")
        net_ids: dict[str, str] = {}
        for n in inst.networks:
            hosts = list(ipaddress.ip_network(n.cidr).hosts())
            pname = f"{inst.instance_name}-{n.network_name}"
            nid = provider.create_network(NetworkConfig(
                name=pname, cidr=n.cidr, gateway=str(hosts[0]), internet=n.isolation_policy == "internet",
                labels={"clpe.instance": inst.instance_name}))
            n.provider_identifier = nid
            net_ids[n.network_name] = pname
            rollback.append(lambda nid=nid: provider.delete_network(nid))
            event(db, inst, "network_created", network=n.network_name, cidr=n.cidr, policy=n.isolation_policy)
        db.commit()

        for m in inst.machines:
            t = templates[m.machine_template_id]
            m.status = "PREPARING"
            vm_id = provider.create_vm(VMConfig(
                name=f"{inst.instance_name}-{m.name}", hostname=m.name, image=t.image_reference,
                cpu=m.cpu_limit, ram_mb=m.ram_limit, role=m.role, checksum=t.image_checksum,
                networks={net_ids[k]: ip for k, ip in m.ip_addresses.items()}, meta=dict(t.meta or {}),
                labels={"clpe.instance": inst.instance_name, "clpe.machine": m.name},
            ))
            m.vm_identifier = vm_id
            m.status = "CREATED"
            rollback.append(lambda vm_id=vm_id: provider.delete_vm(vm_id))
            event(db, inst, "vm_created", machine=m.name, template=t.slug, ips=m.ip_addresses)
            db.commit()

        set_status(db, inst, "STARTING")
        for m in inst.machines:
            m.status = "STARTING"
            provider.start_vm(m.vm_identifier)
            m.status = "RUNNING"
            event(db, inst, "vm_started", machine=m.name)
            db.commit()

        if cfg.get("cleanup", {}).get("snapshot_restore", True):
            for m in inst.machines:
                try:
                    sid = provider.create_snapshot(m.vm_identifier, "initial")
                    db.add(LabSnapshot(lab_machine_id=m.id, snapshot_name="initial", snapshot_identifier=sid))
                except ProviderError as e:
                    event(db, inst, "warning", machine=m.name, message=f"Boshlang'ich snapshot olinmadi: {e}")
            db.commit()

        inst.started_at = now()
        inst.expires_at = now() + timedelta(minutes=int(cfg.get("duration_minutes", 60)))
        set_status(db, inst, "RUNNING", message="LAB READY")
    except Exception as e:  # noqa: BLE001 — har qanday xatoda resurslar qaytariladi
        log.exception("Lab start xatosi")
        db.rollback()
        for undo in reversed(rollback):
            try:
                undo()
            except Exception:  # noqa: BLE001
                log.exception("Rollback xatosi")
        inst = db.get(LabInstance, inst.id)
        for m in inst.machines:
            m.status = "ERROR"
        inst.error = str(e)[:1000]
        set_status(db, inst, "ERROR", message=str(e)[:300])


# ------------------------------------------------------------------ to'xtatish / tozalash
def stop_instance(instance_id, reason: str = "user") -> None:
    db = SessionLocal()
    try:
        inst = db.get(LabInstance, instance_id)
        if not inst or inst.status in ("STOPPED", "DELETING"):
            return
        provider = provider_for(inst)
        set_status(db, inst, "STOPPING", reason=reason)
        destroy = inst.template.configuration_json.get("cleanup", {}).get("destroy_on_stop", True)
        for m in inst.machines:
            if not m.vm_identifier:
                continue
            try:
                if destroy:
                    for s in m.snapshots:
                        _drop_snapshot(provider, s.snapshot_identifier)
                    provider.delete_vm(m.vm_identifier)
                else:
                    provider.stop_vm(m.vm_identifier)
            except ProviderError as e:
                event(db, inst, "warning", machine=m.name, message=str(e))
            m.status = "STOPPED"
        if destroy:
            for n in inst.networks:
                if n.provider_identifier:
                    try:
                        provider.delete_network(n.provider_identifier)
                    except ProviderError as e:
                        event(db, inst, "warning", network=n.network_name, message=str(e))
        inst.stopped_at = now()
        set_status(db, inst, "STOPPED", reason=reason)
    finally:
        db.close()
    process_queue()


def _drop_snapshot(provider, snapshot_id: str) -> None:
    if provider.name == "docker":
        try:
            provider.client.images.remove(snapshot_id, force=True)
        except Exception:  # noqa: BLE001
            pass


def process_queue() -> None:
    db = SessionLocal()
    try:
        queued = db.scalars(select(LabInstance).where(LabInstance.status == "QUEUED")
                            .order_by(LabInstance.created_at)).all()
        ids = [q.id for q in queued]
    finally:
        db.close()
    for i in ids:
        start_instance(i)


def cleanup_expired() -> int:
    db = SessionLocal()
    try:
        rows = db.scalars(select(LabInstance).where(LabInstance.status == "RUNNING")).all()
        expired = [r.id for r in rows if r.expires_at and _aware(r.expires_at) < now()]
    finally:
        db.close()
    for i in expired:
        stop_instance(i, reason="timeout")
    return len(expired)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ------------------------------------------------------------------ snapshot / reset
def snapshot_instance(db: Session, inst: LabInstance, name: str) -> list[str]:
    provider = provider_for(inst)
    if inst.status != "RUNNING":
        raise LabError("Snapshot faqat ishlayotgan laboratoriyada olinadi")
    done = []
    for m in inst.machines:
        sid = provider.create_snapshot(m.vm_identifier, name)
        db.add(LabSnapshot(lab_machine_id=m.id, snapshot_name=name, snapshot_identifier=sid))
        done.append(m.name)
    event(db, inst, "snapshot", name=name, machines=done)
    db.commit()
    return done


def restore_instance(instance_id, name: str = "initial") -> None:
    db = SessionLocal()
    try:
        inst = db.get(LabInstance, instance_id)
        if not inst or inst.status != "RUNNING":
            return
        provider = provider_for(inst)
        set_status(db, inst, "RESETTING", snapshot=name)
        try:
            for m in inst.machines:
                snap = next((s for s in sorted(m.snapshots, key=lambda s: s.created_at, reverse=True)
                             if s.snapshot_name == name), None)
                if not snap:
                    raise LabError(f"'{m.name}' uchun '{name}' snapshot topilmadi")
                m.vm_identifier = provider.restore_snapshot(m.vm_identifier, snap.snapshot_identifier)
                event(db, inst, "vm_restored", machine=m.name, snapshot=name)
            set_status(db, inst, "RUNNING", message="Snapshot tiklandi")
        except Exception as e:  # noqa: BLE001
            db.rollback()
            inst = db.get(LabInstance, instance_id)
            inst.error = str(e)[:1000]
            set_status(db, inst, "ERROR", message=str(e)[:300])
    finally:
        db.close()


# ------------------------------------------------------------------ skan
def run_scan(db: Session, inst: LabInstance, user_id, target: str, profile: str) -> LabScan:
    if inst.status != "RUNNING":
        raise LabError("Skan uchun laboratoriya ishlayotgan bo'lishi kerak")
    cidrs = [n.cidr for n in inst.networks]
    target = validate_target(target, cidrs)
    attacker = next((m for m in inst.machines if m.role == "attacker"), None)
    if not attacker:
        raise LabError("Bu laboratoriyada hujumchi mashina yo'q")
    res = provider_for(inst).exec_in_vm(attacker.vm_identifier, build_nmap_argv(profile, target), timeout=600)
    if res.exit_code != 0:
        raise LabError(f"nmap xatosi: {res.output[-300:]}")
    hosts = parse_nmap_xml(res.output, cidrs)
    scan = LabScan(lab_instance_id=inst.id, user_id=user_id, source="engine", target=target, profile=profile,
                   hosts=hosts)
    db.add(scan)
    event(db, inst, "scan", target=target, profile=profile, hosts=len(hosts))
    db.commit()
    return scan


def import_scan(db: Session, inst: LabInstance, user_id, xml: str) -> LabScan:
    cidrs = [n.cidr for n in inst.networks]
    hosts = parse_nmap_xml(xml, cidrs)
    scan = LabScan(lab_instance_id=inst.id, user_id=user_id, source="import", target=",".join(cidrs),
                   profile="import", hosts=hosts)
    db.add(scan)
    event(db, inst, "scan_import", hosts=len(hosts))
    db.commit()
    return scan
