"""Laboratoriya manifesti (YAML/JSON) sxemasi va xavfsizlik siyosati.

Yangi laboratoriya qo'shish = yangi YAML fayl (yoki admin paneldagi YAML muharriri).
Kodni o'zgartirish kerak emas. Spetsifikatsiyadagi qisqa yozuv ham qabul qilinadi:
    machines: [kali-linux, ubuntu-server]
    network: {type: isolated, internet: false}
    tasks: [{id: t1, title: ..., validation: port_discovery}]
"""
from __future__ import annotations

import re
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from app.core.security import hash_flag

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,30}$")

Localized = str | dict[str, str]


class ManifestError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


class NetworkSpec(BaseModel):
    name: str = "lab"
    type: Literal["isolated", "internal", "nat", "bridged"] = "isolated"
    internet: bool = False
    cidr: str | None = None  # bo'sh bo'lsa IPAM ajratadi

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not NAME_RE.match(v):
            raise ValueError("tarmoq nomi faqat kichik harf, raqam va '-' bo'lishi kerak")
        return v


class MachineSpec(BaseModel):
    name: str
    template: str
    role: Literal["attacker", "target", "defender", "service"] = "target"
    networks: list[str] = Field(default_factory=lambda: ["lab"])
    cpu: float | None = None
    ram: int | None = None
    console: bool | None = None  # brauzer terminali (default: attacker uchun yoqiq)
    hidden: bool = False  # topologiyada skan qilinmaguncha yashirin

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not NAME_RE.match(v):
            raise ValueError("mashina nomi faqat kichik harf, raqam va '-' bo'lishi kerak")
        return v


class ValidationSpec(BaseModel):
    type: str
    config: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _shorthand(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"type": data}
        if isinstance(data, dict) and "config" not in data:
            return {"type": data.get("type"), "config": {k: v for k, v in data.items() if k != "type"}}
        return data


class TaskSpec(BaseModel):
    id: str
    title: Localized
    description: Localized = ""
    points: int = 10
    hint: Localized | None = None
    validation: ValidationSpec


class ResourceSpec(BaseModel):
    cpu: float = 2
    ram: int = 2048
    disk: int = 0
    max_machines: int = 6


class ScoringSpec(BaseModel):
    maximum: int = 100
    passing: int = 60
    xp: int = 100


class CleanupSpec(BaseModel):
    snapshot_restore: bool = True
    auto_shutdown: bool = True
    destroy_on_stop: bool = True


class TopologySpec(BaseModel):
    reveal: Literal["full", "discovered"] = "discovered"


class LabManifest(BaseModel):
    id: str
    version: int = 1
    title: Localized
    description: Localized = ""
    category: str = "general"
    course: str | None = None
    lab_type: Literal["offensive", "defensive", "forensics", "malware", "general"] = "offensive"
    difficulty: Literal["beginner", "intermediate", "advanced"] = "beginner"
    duration_minutes: int = 60
    objectives: list[Localized] = Field(default_factory=list)
    instructions: Localized = ""
    machines: list[MachineSpec]
    networks: list[NetworkSpec] = Field(default_factory=lambda: [NetworkSpec()])
    topology: TopologySpec = Field(default_factory=TopologySpec)
    resources: ResourceSpec = Field(default_factory=ResourceSpec)
    tasks: list[TaskSpec] = Field(default_factory=list)
    scoring: ScoringSpec = Field(default_factory=ScoringSpec)
    cleanup: CleanupSpec = Field(default_factory=CleanupSpec)

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if "network" in data and "networks" not in data:
            data["networks"] = [{"name": "lab", **(data.pop("network") or {})}]
        machines = []
        for i, m in enumerate(data.get("machines") or []):
            if isinstance(m, str):
                role = "attacker" if i == 0 else "target"
                m = {"name": m.replace("_", "-")[:31], "template": m, "role": role}
            machines.append(m)
        data["machines"] = machines
        if isinstance(data.get("scoring"), dict) and "max" in data["scoring"]:
            data["scoring"]["maximum"] = data["scoring"].pop("max")
        return data

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not SLUG_RE.match(v):
            raise ValueError("id faqat kichik harf, raqam va '-' (2-63 belgi)")
        return v


def localize(value: Localized | None, lang: str = "uz") -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.get(lang) or value.get("uz") or value.get("en") or next(iter(value.values()), "")


def parse_manifest(text: str, *, known_templates: set[str] | None = None,
                   allow_internet: bool = False, validator_types: set[str] | None = None) -> LabManifest:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ManifestError([f"YAML xatosi: {e}"]) from e
    if not isinstance(data, dict):
        raise ManifestError(["Manifest YAML obyekt (key: value) bo'lishi kerak"])
    try:
        m = LabManifest.model_validate(data)
    except ValidationError as e:
        raise ManifestError([f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()]) from e
    errors = check_policy(m, known_templates=known_templates, allow_internet=allow_internet,
                          validator_types=validator_types)
    if errors:
        raise ManifestError(errors)
    return m


def check_policy(m: LabManifest, *, known_templates: set[str] | None, allow_internet: bool,
                 validator_types: set[str] | None) -> list[str]:
    """Spetsifikatsiya 9-bo'lim: izolyatsiya qoidalari."""
    errors: list[str] = []
    net_names = {n.name for n in m.networks}
    if len(net_names) != len(m.networks):
        errors.append("tarmoq nomlari takrorlanmasligi kerak")
    for n in m.networks:
        if n.type == "bridged":
            errors.append(f"tarmoq '{n.name}': bridged networking taqiqlangan (9.3)")
        if (n.internet or n.type == "nat") and not allow_internet:
            errors.append(f"tarmoq '{n.name}': internetga chiqish platforma sozlamasida o'chirilgan (9.6)")
        if m.lab_type == "malware" and (n.internet or n.type != "isolated"):
            errors.append(f"tarmoq '{n.name}': malware laboratoriyasi faqat to'liq izolyatsiyalangan bo'ladi (9.7)")
    names = [x.name for x in m.machines]
    if not m.machines:
        errors.append("kamida bitta mashina kerak")
    if len(set(names)) != len(names):
        errors.append("mashina nomlari takrorlanmasligi kerak")
    if len(m.machines) > m.resources.max_machines:
        errors.append(f"mashinalar soni {m.resources.max_machines} dan oshmasligi kerak (9.9)")
    for mach in m.machines:
        if known_templates is not None and mach.template not in known_templates:
            errors.append(f"mashina '{mach.name}': noma'lum VM shabloni '{mach.template}'")
        for net in mach.networks:
            if net not in net_names:
                errors.append(f"mashina '{mach.name}': noma'lum tarmoq '{net}'")
    task_ids = [t.id for t in m.tasks]
    if len(set(task_ids)) != len(task_ids):
        errors.append("topshiriq id'lari takrorlanmasligi kerak")
    for t in m.tasks:
        if validator_types is not None and t.validation.type not in validator_types:
            errors.append(f"topshiriq '{t.id}': noma'lum tekshiruv turi '{t.validation.type}'")
        ref = t.validation.config.get("machine")
        if ref and ref not in names:
            errors.append(f"topshiriq '{t.id}': noma'lum mashina '{ref}'")
    return errors


def to_storage(m: LabManifest) -> dict[str, Any]:
    """DB'ga yoziladigan konfiguratsiya: ochiq flag/javoblar xeshlanadi."""
    data = m.model_dump(mode="json")
    for t in data["tasks"]:
        cfg = t["validation"]["config"]
        if "flag" in cfg:
            cfg["flag_hash"] = hash_flag(str(cfg.pop("flag")))
        if "answers" in cfg:
            cs = bool(cfg.get("case_sensitive", False))
            cfg["answer_hashes"] = [hash_flag(a if cs else str(a).strip().lower()) for a in cfg.pop("answers")]
    return data


def public_view(config: dict[str, Any], lang: str = "uz") -> dict[str, Any]:
    """Talabaga ko'rsatiladigan qism: tekshiruv sirlari olib tashlanadi."""
    hidden_keys = {"flag_hash", "answer_hashes", "expected_ports", "expected", "path", "contains", "process"}
    tasks = []
    for t in config.get("tasks", []):
        cfg = {k: v for k, v in t["validation"]["config"].items() if k not in hidden_keys}
        tasks.append({
            "id": t["id"], "title": localize(t["title"], lang), "description": localize(t["description"], lang),
            "hint": localize(t.get("hint"), lang) or None, "points": t["points"],
            "validation_type": t["validation"]["type"], "input": cfg.get("input", _default_input(t["validation"]["type"])),
            "machine": cfg.get("machine"),
        })
    return {
        "id": config["id"], "title": localize(config["title"], lang),
        "description": localize(config["description"], lang), "category": config["category"],
        "course": config.get("course"), "lab_type": config["lab_type"], "difficulty": config["difficulty"],
        "duration_minutes": config["duration_minutes"],
        "objectives": [localize(o, lang) for o in config.get("objectives", [])],
        "instructions": localize(config.get("instructions"), lang),
        "machines": [{"name": x["name"], "template": x["template"], "role": x["role"]} for x in config["machines"]
                     if not x.get("hidden") or x["role"] == "attacker"],
        "networks": [{"name": n["name"], "type": n["type"], "internet": n["internet"]} for n in config["networks"]],
        "resources": config["resources"], "scoring": config["scoring"], "tasks": tasks,
    }


def _default_input(vtype: str) -> str:
    return {"port_discovery": "ports", "host_discovery": "hosts", "flag": "text", "answer": "text"}.get(vtype, "none")
