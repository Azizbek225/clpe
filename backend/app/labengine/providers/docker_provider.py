"""Docker adapteri: DVWA, Juice Shop, Metasploitable2 kabi nishon serverlar va hujumchi konteyner.

Izolyatsiya:
- har bir laboratoriya tarmog'i `internal=True` (tashqi marshrut yo'q, internet yopiq);
- host'ga hech qanday port chiqarilmaydi, volume ulanmaydi, `privileged` taqiqlangan;
- CPU/RAM/PID limitlari qo'yiladi.
"""
from __future__ import annotations

import json

from app.labengine.providers.base import (
    ExecResult, NetworkConfig, ProviderError, VirtualizationProvider, VMConfig, VMMetrics, safe_id,
)

LABEL = "clpe.managed"


class DockerProvider(VirtualizationProvider):
    name = "docker"
    supports_console = True

    def __init__(self) -> None:
        try:
            import docker
            from docker.types import IPAMConfig, IPAMPool
        except ImportError as e:  # pragma: no cover
            raise ProviderError("docker python paketi o'rnatilmagan") from e
        self._docker = docker
        self._IPAMConfig, self._IPAMPool = IPAMConfig, IPAMPool
        self.client = docker.from_env()

    # ---------- tarmoq ----------
    def create_network(self, config: NetworkConfig) -> str:
        safe_id(config.name)
        ipam = self._IPAMConfig(pool_configs=[self._IPAMPool(subnet=config.cidr, gateway=config.gateway)])
        net = self.client.networks.create(
            config.name, driver="bridge", internal=not config.internet, ipam=ipam, check_duplicate=True,
            labels={LABEL: "1", **config.labels},
            options={"com.docker.network.bridge.enable_ip_masquerade": "true" if config.internet else "false"},
        )
        return net.id

    def delete_network(self, network_id: str) -> None:
        try:
            self.client.networks.get(safe_id(network_id)).remove()
        except self._docker.errors.NotFound:
            pass

    # ---------- VM (konteyner) ----------
    def verify_image(self, image: str, checksum: str | None) -> None:
        try:
            img = self.client.images.get(image)
        except self._docker.errors.ImageNotFound:
            img = self.client.images.pull(image)
        if checksum:
            digests = {img.id, *[d.split("@", 1)[-1] for d in img.attrs.get("RepoDigests", [])]}
            if checksum not in digests:
                raise ProviderError(f"Tasvir checksumi mos emas: {image}")

    def create_vm(self, config: VMConfig) -> str:
        safe_id(config.name)
        self.verify_image(config.image, config.checksum)
        return self._create_container(config, config.image)

    def _create_container(self, config: VMConfig, image: str) -> str:
        nets = list(config.networks.items())
        first_net, first_ip = nets[0]
        meta = config.meta
        container = self.client.containers.create(
            image,
            name=config.name,
            hostname=config.hostname,
            command=meta.get("command"),
            entrypoint=meta.get("entrypoint"),
            environment=meta.get("environment") or {},
            tty=bool(meta.get("tty", True)),
            stdin_open=True,
            detach=True,
            nano_cpus=int(config.cpu * 1e9),
            mem_limit=f"{config.ram_mb}m",
            pids_limit=int(meta.get("pids_limit", 512)),
            privileged=False,
            cap_add=[c for c in meta.get("cap_add", []) if c in {"NET_RAW", "NET_ADMIN"}],
            security_opt=["no-new-privileges"] if config.role == "attacker" else None,
            labels={LABEL: "1", "clpe.config": json.dumps(_cfg_dict(config)), **config.labels},
            network=first_net,
            # Diqqat: ports= berilmaydi — host'ga hech narsa ochilmaydi.
        )
        api = self.client.api
        api.disconnect_container_from_network(container.id, first_net)
        api.connect_container_to_network(container.id, first_net, ipv4_address=first_ip,
                                         aliases=[config.hostname])
        for net, ip in nets[1:]:
            api.connect_container_to_network(container.id, net, ipv4_address=ip, aliases=[config.hostname])
        return container.id

    def _get(self, vm_id: str):
        try:
            return self.client.containers.get(safe_id(vm_id))
        except self._docker.errors.NotFound as e:
            raise ProviderError(f"Konteyner topilmadi: {vm_id}") from e

    def start_vm(self, vm_id: str) -> None:
        self._get(vm_id).start()

    def stop_vm(self, vm_id: str) -> None:
        self._get(vm_id).stop(timeout=10)

    def delete_vm(self, vm_id: str) -> None:
        try:
            self._get(vm_id).remove(force=True)
        except ProviderError:
            pass

    def create_snapshot(self, vm_id: str, name: str) -> str:
        c = self._get(vm_id)
        repo = f"clpe-snapshot/{c.name}"
        tag = safe_id(name).lower()
        c.commit(repository=repo, tag=tag, conf={"Labels": {LABEL: "1"}})
        return f"{repo}:{tag}"

    def restore_snapshot(self, vm_id: str, snapshot_id: str) -> str:
        c = self._get(vm_id)
        cfg = _cfg_from_dict(json.loads(c.labels["clpe.config"]))
        c.remove(force=True)
        new_id = self._create_container(cfg, snapshot_id)
        self.start_vm(new_id)
        return new_id

    def get_vm_status(self, vm_id: str) -> str:
        try:
            state = self._get(vm_id).status
        except ProviderError:
            return "DELETED"
        return {"running": "RUNNING", "paused": "PAUSED", "created": "CREATED",
                "exited": "STOPPED", "restarting": "STARTING"}.get(state, "ERROR")

    def get_vm_metrics(self, vm_id: str) -> VMMetrics:
        s = self._get(vm_id).stats(stream=False)
        cpu = s["cpu_stats"]
        pre = s["precpu_stats"]
        cpu_delta = cpu["cpu_usage"]["total_usage"] - pre["cpu_usage"]["total_usage"]
        sys_delta = cpu.get("system_cpu_usage", 0) - pre.get("system_cpu_usage", 0)
        ncpu = cpu.get("online_cpus", 1)
        pct = (cpu_delta / sys_delta) * ncpu * 100 if sys_delta > 0 else 0.0
        mem = s.get("memory_stats", {})
        return VMMetrics(cpu_percent=round(pct, 1), ram_used_mb=round(mem.get("usage", 0) / 2**20, 1),
                         ram_limit_mb=round(mem.get("limit", 0) / 2**20, 1))

    def exec_in_vm(self, vm_id: str, argv: list[str], timeout: int = 120) -> ExecResult:
        # Konteyner ICHIDA bajariladi (host'da emas). argv ro'yxat — shell interpolatsiya yo'q.
        res = self._get(vm_id).exec_run(argv, demux=False)
        return ExecResult(res.exit_code, (res.output or b"").decode(errors="replace"))

    def open_console(self, vm_id: str, shell: str = "/bin/bash"):
        """Brauzer terminali uchun konteyner ichida interaktiv shell (raw socket)."""
        api = self.client.api
        exec_id = api.exec_create(self._get(vm_id).id, [shell], stdin=True, tty=True)["Id"]
        sock = api.exec_start(exec_id, socket=True, tty=True)
        return exec_id, getattr(sock, "_sock", sock)

    def resize_console(self, exec_id: str, rows: int, cols: int) -> None:
        self.client.api.exec_resize(exec_id, height=rows, width=cols)

    def used_cidrs(self) -> list[str]:
        out = []
        for n in self.client.networks.list():
            for cfg in (n.attrs.get("IPAM") or {}).get("Config") or []:
                if cfg.get("Subnet") and ":" not in cfg["Subnet"]:
                    out.append(cfg["Subnet"])
        return out

    def healthcheck(self) -> dict:
        return {"provider": self.name, "ok": bool(self.client.ping()), "version": self.client.version().get("Version")}


def _cfg_dict(c: VMConfig) -> dict:
    return {"name": c.name, "hostname": c.hostname, "image": c.image, "cpu": c.cpu, "ram_mb": c.ram_mb,
            "networks": c.networks, "role": c.role, "meta": c.meta}


def _cfg_from_dict(d: dict) -> VMConfig:
    return VMConfig(name=d["name"], hostname=d["hostname"], image=d["image"], cpu=d["cpu"], ram_mb=d["ram_mb"],
                    networks=d["networks"], role=d["role"], meta=d.get("meta", {}))
