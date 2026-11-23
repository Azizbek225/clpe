"""VirtualBox adapteri (Windows host). VBoxManage CLI orqali, faqat argumentlar ro'yxati bilan.

Tarmoq: faqat `intnet` (Internal Network) — VM'lar faqat bir-biri bilan gaplashadi.
Bridged va host-only rejimlar ishlatilmaydi (9.3, 9.4).
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
import shutil
import subprocess
from pathlib import Path

from app.labengine.providers.base import (
    ExecResult, NetworkConfig, ProviderError, VirtualizationProvider, VMConfig, VMMetrics, safe_id,
)


class VirtualBoxProvider(VirtualizationProvider):
    name = "virtualbox"

    def __init__(self, vboxmanage: str | None = None) -> None:
        self.bin = vboxmanage or shutil.which("VBoxManage") or shutil.which("vboxmanage")
        if not self.bin:
            raise ProviderError("VBoxManage topilmadi — VirtualBox o'rnatilganini tekshiring")

    def _run(self, *args: str, timeout: int = 300) -> str:
        proc = subprocess.run([self.bin, *args], capture_output=True, text=True, timeout=timeout, shell=False)
        if proc.returncode != 0:
            raise ProviderError(f"VBoxManage {args[0]}: {proc.stderr.strip()[:500]}")
        return proc.stdout

    # Internal network VirtualBox'da alohida obyekt emas — NIC'ga nom berilganda paydo bo'ladi.
    def create_network(self, config: NetworkConfig) -> str:
        ipaddress.ip_network(config.cidr)
        if config.internet:
            raise ProviderError("VirtualBox adapteri internetli laboratoriyalarni qo'llab-quvvatlamaydi")
        return safe_id(config.name)

    def delete_network(self, network_id: str) -> None:
        return None

    def verify_image(self, image: str, checksum: str | None) -> None:
        if checksum and Path(image).is_file():
            h = hashlib.sha256()
            with open(image, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            if h.hexdigest() != checksum.removeprefix("sha256:"):
                raise ProviderError(f"Tasvir checksumi mos emas: {image}")

    def create_vm(self, config: VMConfig) -> str:
        """`image` — oldindan import qilingan bazaviy VM nomi (shablon). Linked clone yaratiladi."""
        base = safe_id(config.image)
        name = safe_id(config.name)
        self._run("snapshot", base, "list")  # bazaviy snapshot mavjudligini tekshirish
        self._run("clonevm", base, "--snapshot", "base", "--options", "link", "--name", name, "--register")
        self._run("modifyvm", name, "--cpus", str(max(1, int(config.cpu))), "--memory", str(config.ram_mb),
                  "--clipboard-mode", "disabled", "--draganddrop", "disabled", "--vrde", "off")
        for idx, (net, _ip) in enumerate(config.networks.items(), start=1):
            self._run("modifyvm", name, f"--nic{idx}", "intnet", f"--intnet{idx}", safe_id(net))
        for idx in range(len(config.networks) + 1, 5):
            self._run("modifyvm", name, f"--nic{idx}", "none")
        return name

    def start_vm(self, vm_id: str) -> None:
        self._run("startvm", safe_id(vm_id), "--type", "headless")

    def stop_vm(self, vm_id: str) -> None:
        self._run("controlvm", safe_id(vm_id), "poweroff")

    def delete_vm(self, vm_id: str) -> None:
        try:
            self._run("unregistervm", safe_id(vm_id), "--delete")
        except ProviderError:
            pass

    def create_snapshot(self, vm_id: str, name: str) -> str:
        self._run("snapshot", safe_id(vm_id), "take", safe_id(name))
        return name

    def restore_snapshot(self, vm_id: str, snapshot_id: str) -> str:
        vm = safe_id(vm_id)
        if self.get_vm_status(vm) == "RUNNING":
            self.stop_vm(vm)
        self._run("snapshot", vm, "restore", safe_id(snapshot_id))
        self.start_vm(vm)
        return vm

    def get_vm_status(self, vm_id: str) -> str:
        try:
            out = self._run("showvminfo", safe_id(vm_id), "--machinereadable")
        except ProviderError:
            return "DELETED"
        m = re.search(r'^VMState="(\w+)"', out, re.M)
        state = m.group(1) if m else "unknown"
        return {"running": "RUNNING", "paused": "PAUSED", "poweroff": "STOPPED", "saved": "STOPPED",
                "starting": "STARTING", "stopping": "STOPPING", "restoring": "RESETTING"}.get(state, "ERROR")

    def get_vm_metrics(self, vm_id: str) -> VMMetrics:
        out = self._run("metrics", "query", safe_id(vm_id), "Guest/CPU/Load/User,Guest/RAM/Usage/Total,Guest/RAM/Usage/Free")
        nums = {m.group(1): float(m.group(2)) for m in re.finditer(r"(Guest/\S+)\s+([\d.]+)", out)}
        total = nums.get("Guest/RAM/Usage/Total", 0) / 1024
        free = nums.get("Guest/RAM/Usage/Free", 0) / 1024
        return VMMetrics(cpu_percent=nums.get("Guest/CPU/Load/User", 0.0), ram_used_mb=total - free, ram_limit_mb=total)

    def exec_in_vm(self, vm_id: str, argv: list[str], timeout: int = 120) -> ExecResult:
        # Guest Additions orqali VM ICHIDA. Login ma'lumotlari shablon meta'sidan olinishi rejalashtirilgan.
        raise ProviderError("VirtualBox guestcontrol integratsiyasi keyingi bosqichda (nmap XML importidan foydalaning)")
