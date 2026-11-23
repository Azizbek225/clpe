"""Virtualizatsiya provayderi interfeysi (spetsifikatsiya 8.1).

Har bir adapter (Docker, VirtualBox, libvirt, Mock) shu sinfni amalga oshiradi.
Yangi provayder qo'shish uchun: shu sinfdan meros oling va `register_provider` bilan ro'yxatga oling
(yoki CLPE_PLUGIN_MODULES orqali tashqi modulda) — yadro kodi o'zgarmaydi.

Xavfsizlik qoidasi (9-bo'lim): adapterlar foydalanuvchidan kelgan shell buyrug'ini HOST'da
hech qachon bajarmaydi. Tashqi jarayonlar faqat argumentlar ro'yxati (shell=False) bilan,
tekshirilgan identifikatorlar bilan chaqiriladi.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class ProviderError(RuntimeError):
    pass


class NotSupported(ProviderError):
    pass


def safe_id(value: str) -> str:
    if not SAFE_ID.match(value or ""):
        raise ProviderError(f"Ruxsat etilmagan identifikator: {value!r}")
    return value


@dataclass
class NetworkConfig:
    name: str  # provayderdagi to'liq nom, masalan clpe-<instance>-lab
    cidr: str
    gateway: str
    internet: bool = False
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class VMConfig:
    name: str  # provayderdagi to'liq nom
    hostname: str
    image: str
    cpu: float
    ram_mb: int
    networks: dict[str, str]  # provider network name -> ip
    role: str = "target"
    disk_gb: int = 0
    checksum: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class VMMetrics:
    cpu_percent: float
    ram_used_mb: float
    ram_limit_mb: float


@dataclass
class ExecResult:
    exit_code: int
    output: str


class VirtualizationProvider(ABC):
    name: str = "base"
    supports_console: bool = False

    # --- VM hayot sikli (8.1) ---
    @abstractmethod
    def create_vm(self, config: VMConfig) -> str: ...

    @abstractmethod
    def start_vm(self, vm_id: str) -> None: ...

    @abstractmethod
    def stop_vm(self, vm_id: str) -> None: ...

    @abstractmethod
    def delete_vm(self, vm_id: str) -> None: ...

    @abstractmethod
    def create_snapshot(self, vm_id: str, name: str) -> str: ...

    @abstractmethod
    def restore_snapshot(self, vm_id: str, snapshot_id: str) -> str:
        """Tiklangandan keyingi vm_id ni qaytaradi (Docker'da konteyner qayta yaratiladi)."""

    @abstractmethod
    def get_vm_status(self, vm_id: str) -> str: ...

    @abstractmethod
    def get_vm_metrics(self, vm_id: str) -> VMMetrics: ...

    # --- Tarmoq ---
    @abstractmethod
    def create_network(self, config: NetworkConfig) -> str: ...

    @abstractmethod
    def delete_network(self, network_id: str) -> None: ...

    # --- Lab ichidagi qat'iy belgilangan amallar (host'da emas!) ---
    def exec_in_vm(self, vm_id: str, argv: list[str], timeout: int = 120) -> ExecResult:
        """Faqat orkestrator chaqiradi; argv orkestratorda oq ro'yxat asosida quriladi."""
        raise NotSupported(f"{self.name}: VM ichida buyruq bajarish qo'llab-quvvatlanmaydi")

    def verify_image(self, image: str, checksum: str | None) -> None:
        """Tasvir checksumini tekshirish (9.11). Mos kelmasa ProviderError."""

    def used_cidrs(self) -> list[str]:
        """Host'da allaqachon band bo'lgan subnetlar (IPAM to'qnashuvining oldini olish uchun)."""
        return []

    def healthcheck(self) -> dict[str, Any]:
        return {"provider": self.name, "ok": True}
