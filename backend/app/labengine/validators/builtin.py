"""O'rnatilgan validatorlar: flag, answer, port_discovery, host_discovery, scan_coverage, vm_check, manual."""
from __future__ import annotations

import re

from app.core.security import flags_equal, hash_flag
from app.labengine.providers.base import ProviderError
from app.labengine.scanner import merge_hosts
from app.labengine.validators import register_validator
from app.labengine.validators.base import ValidationContext, ValidationResult

SAFE_PATH = re.compile(r"^/[A-Za-z0-9_./-]{1,200}$")


def _ratio_result(found: int, total: int, ctx: ValidationContext, what: str) -> ValidationResult:
    if total == 0:
        return ValidationResult(False, 0, "Topshiriq noto'g'ri sozlangan")
    min_ratio = float(ctx.config.get("min_ratio", 1.0))
    ratio = found / total
    score = round(ctx.max_score * ratio)
    passed = ratio >= min_ratio
    return ValidationResult(passed, score if passed else round(score / 2),
                            f"{found}/{total} {what} to'g'ri topildi" + ("" if passed else " — yana urinib ko'ring"))


@register_validator("flag")
def flag(ctx: ValidationContext) -> ValidationResult:
    value = str(ctx.submitted.get("value", "")).strip()
    if value and flags_equal(value, ctx.config.get("flag_hash", "")):
        return ValidationResult(True, ctx.max_score, "Flag to'g'ri! 🎯")
    return ValidationResult(False, 0, "Flag noto'g'ri")


@register_validator("answer")
def answer(ctx: ValidationContext) -> ValidationResult:
    value = str(ctx.submitted.get("value", "")).strip()
    if not ctx.config.get("case_sensitive"):
        value = value.lower()
    if hash_flag(value) in set(ctx.config.get("answer_hashes", [])):
        return ValidationResult(True, ctx.max_score, "Javob to'g'ri")
    return ValidationResult(False, 0, "Javob noto'g'ri")


def _expected_ports(ctx: ValidationContext) -> set[int]:
    if ctx.config.get("expected_ports"):
        return {int(p) for p in ctx.config["expected_ports"]}
    m = ctx.machine()
    tmpl_ports = (ctx.config.get("_template_meta") or {}).get("mock_ports", [])
    return {int(p["port"]) for p in tmpl_ports} if m else set()


@register_validator("port_discovery")
def port_discovery(ctx: ValidationContext) -> ValidationResult:
    """Talaba nishondagi ochiq portlarni sanab beradi: {"ports": [21, 22, 80]}."""
    expected = _expected_ports(ctx)
    try:
        submitted = {int(p) for p in ctx.submitted.get("ports", [])}
    except (TypeError, ValueError):
        return ValidationResult(False, 0, "Portlar raqam bo'lishi kerak")
    wrong = submitted - expected
    found = len(submitted & expected)
    res = _ratio_result(found, len(expected), ctx, "port")
    if wrong:
        res.feedback += f"; {len(wrong)} ta port noto'g'ri"
        res.score = max(0, res.score - len(wrong) * 2)
    return res


@register_validator("host_discovery")
def host_discovery(ctx: ValidationContext) -> ValidationResult:
    """Talaba tarmoqdagi tirik hostlar IP'larini yuboradi: {"hosts": ["10.200.0.10", ...]}."""
    targets = {ip for m in ctx.instance.machines if m.role != "attacker" for ip in (m.ip_addresses or {}).values()}
    submitted = {str(h).strip() for h in ctx.submitted.get("hosts", [])}
    res = _ratio_result(len(submitted & targets), len(targets), ctx, "host")
    if submitted - targets:
        res.feedback += f"; {len(submitted - targets)} ta IP noto'g'ri"
    return res


@register_validator("scan_coverage")
def scan_coverage(ctx: ValidationContext) -> ValidationResult:
    """Talaba skaner bilan nishon(lar)ni topgan bo'lishi kerak (topologiya grafigida ko'rinadi)."""
    merged = merge_hosts(ctx.scans)
    names = ctx.config.get("machines") or [m.name for m in ctx.instance.machines if m.role != "attacker"]
    need_services = bool(ctx.config.get("require_services"))
    total = found = 0
    for m in ctx.instance.machines:
        if m.name not in names:
            continue
        total += 1
        hit = [merged[ip] for ip in (m.ip_addresses or {}).values() if ip in merged]
        if hit and (not need_services or any(p.get("product") for p in hit[0]["ports"])):
            found += 1
    return _ratio_result(found, total, ctx, "nishon")


@register_validator("vm_check")
def vm_check(ctx: ValidationContext) -> ValidationResult:
    """Lab mashinasi ICHIDA oldindan belgilangan tekshiruv. Ruxsat etilgan turlar: file_exists, file_absent."""
    m = ctx.machine()
    if not m or not m.vm_identifier:
        return ValidationResult(False, 0, "Mashina topilmadi")
    check = ctx.config.get("check", "file_exists")
    path = str(ctx.config.get("path", ""))
    if check not in {"file_exists", "file_absent"} or not SAFE_PATH.match(path):
        return ValidationResult(False, 0, "Tekshiruv noto'g'ri sozlangan")
    try:
        res = ctx.provider.exec_in_vm(m.vm_identifier, ["test", "-e", path], timeout=20)
    except ProviderError as e:
        return ValidationResult(False, 0, f"Tekshirib bo'lmadi: {e}")
    ok = (res.exit_code == 0) == (check == "file_exists")
    return ValidationResult(ok, ctx.max_score if ok else 0,
                            "Holat tasdiqlandi ✅" if ok else "Kutilgan holat hali yo'q")


@register_validator("manual")
def manual(ctx: ValidationContext) -> ValidationResult:
    """Hisobot/izoh — Evaluator qo'lda baholaydi."""
    if not str(ctx.submitted.get("value", "")).strip():
        return ValidationResult(False, 0, "Hisobot bo'sh")
    return ValidationResult(False, 0, "Qabul qilindi, o'qituvchi baholaydi", pending=True)
