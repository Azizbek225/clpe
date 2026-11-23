"""Mock provayder: Docker/VM bo'lmagan muhitda (dev, testlar, demo) to'liq oqimni simulyatsiya qiladi.
Skan natijalari shablondagi `meta.mock_ports` asosida nmap XML ko'rinishida generatsiya qilinadi."""
from __future__ import annotations

import threading
import uuid
from xml.sax.saxutils import escape

from app.labengine.providers.base import (
    ExecResult, NetworkConfig, NotSupported, ProviderError, VirtualizationProvider, VMConfig, VMMetrics,
)

_lock = threading.Lock()
_VMS: dict[str, dict] = {}
_NETS: dict[str, NetworkConfig] = {}


class MockProvider(VirtualizationProvider):
    name = "mock"

    def create_network(self, config: NetworkConfig) -> str:
        with _lock:
            _NETS[config.name] = config
        return config.name

    def delete_network(self, network_id: str) -> None:
        with _lock:
            _NETS.pop(network_id, None)

    def create_vm(self, config: VMConfig) -> str:
        if config.meta.get("mock_fail"):
            raise ProviderError("mock: shablon ataylab xato beradi")
        vm_id = f"mock-{uuid.uuid4().hex[:12]}"
        with _lock:
            _VMS[vm_id] = {"config": config, "status": "STOPPED", "snapshots": {}, "files": set(config.meta.get("mock_files", []))}
        return vm_id

    def _vm(self, vm_id: str) -> dict:
        if vm_id not in _VMS:
            raise ProviderError(f"mock: VM topilmadi {vm_id}")
        return _VMS[vm_id]

    def start_vm(self, vm_id: str) -> None:
        self._vm(vm_id)["status"] = "RUNNING"

    def stop_vm(self, vm_id: str) -> None:
        self._vm(vm_id)["status"] = "STOPPED"

    def delete_vm(self, vm_id: str) -> None:
        with _lock:
            _VMS.pop(vm_id, None)

    def create_snapshot(self, vm_id: str, name: str) -> str:
        vm = self._vm(vm_id)
        snap = f"{vm_id}@{name}"
        vm["snapshots"][snap] = set(vm["files"])
        return snap

    def restore_snapshot(self, vm_id: str, snapshot_id: str) -> str:
        vm = self._vm(vm_id)
        if snapshot_id not in vm["snapshots"]:
            raise ProviderError("mock: snapshot topilmadi")
        vm["files"] = set(vm["snapshots"][snapshot_id])
        return vm_id

    def get_vm_status(self, vm_id: str) -> str:
        return _VMS.get(vm_id, {}).get("status", "DELETED")

    def get_vm_metrics(self, vm_id: str) -> VMMetrics:
        cfg: VMConfig = self._vm(vm_id)["config"]
        h = int(vm_id[-4:], 16)
        return VMMetrics(cpu_percent=round(3 + h % 40, 1), ram_used_mb=round(cfg.ram_mb * (0.2 + (h % 50) / 100), 1),
                         ram_limit_mb=cfg.ram_mb)

    def exec_in_vm(self, vm_id: str, argv: list[str], timeout: int = 120) -> ExecResult:
        if argv and argv[0] == "nmap":
            return ExecResult(0, self._fake_nmap(argv[-1], ping_only="-sn" in argv, versions="-sV" in argv))
        if argv[:2] == ["test", "-e"]:
            return ExecResult(0 if argv[2] in self._vm(vm_id)["files"] else 1, "")
        raise NotSupported("mock: faqat nmap va fayl tekshiruvi simulyatsiya qilinadi")

    # test/demo uchun: talaba harakatini simulyatsiya qilish
    def touch_file(self, vm_id: str, path: str) -> None:
        self._vm(vm_id)["files"].add(path)

    def remove_file(self, vm_id: str, path: str) -> None:
        self._vm(vm_id)["files"].discard(path)

    def _fake_nmap(self, target: str, ping_only: bool, versions: bool) -> str:
        import ipaddress
        net = ipaddress.ip_network(target, strict=False)
        hosts = []
        for vm in list(_VMS.values()):
            cfg: VMConfig = vm["config"]
            if vm["status"] != "RUNNING":
                continue
            for ip in cfg.networks.values():
                if ipaddress.ip_address(ip) in net:
                    hosts.append((ip, cfg))
        out = ['<?xml version="1.0"?><nmaprun scanner="nmap" args="mock">']
        for ip, cfg in sorted(hosts, key=lambda x: ipaddress.ip_address(x[0])):
            out.append(f'<host><status state="up"/><address addr="{ip}" addrtype="ipv4"/>')
            out.append(f'<hostnames><hostname name="{escape(cfg.hostname)}" type="PTR"/></hostnames>')
            if not ping_only:
                out.append("<ports>")
                for p in cfg.meta.get("mock_ports", []):
                    prod = f' product="{escape(p.get("product", ""))}" version="{escape(p.get("version", ""))}"' if versions else ""
                    out.append(
                        f'<port protocol="{p.get("protocol", "tcp")}" portid="{p["port"]}"><state state="open"/>'
                        f'<service name="{escape(p.get("service", ""))}"{prod}/></port>')
                out.append("</ports>")
                if versions and cfg.meta.get("os"):
                    out.append(f'<os><osmatch name="{escape(cfg.meta["os"])}" accuracy="95"/></os>')
            out.append("</host>")
        out.append("</nmaprun>")
        return "".join(out)
