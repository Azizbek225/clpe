"""libvirt + QEMU/KVM adapteri (Linux host).

Tarmoq: `<forward>` elementisiz libvirt tarmog'i = to'liq izolyatsiya (internet va host LAN yo'q).
Diskl: qcow2 backing-file (linked clone). Snapshot: internal qcow2 snapshot.
"""
from __future__ import annotations

import ipaddress
from xml.sax.saxutils import escape

from app.labengine.providers.base import (
    NetworkConfig, ProviderError, VirtualizationProvider, VMConfig, VMMetrics, safe_id,
)


class LibvirtProvider(VirtualizationProvider):
    name = "libvirt"

    def __init__(self, uri: str = "qemu:///system", storage_dir: str = "/var/lib/clpe/disks") -> None:
        try:
            import libvirt  # type: ignore
        except ImportError as e:
            raise ProviderError("libvirt-python o'rnatilmagan (pip install libvirt-python)") from e
        self.libvirt = libvirt
        self.conn = libvirt.open(uri)
        self.storage_dir = storage_dir

    def create_network(self, config: NetworkConfig) -> str:
        if config.internet:
            raise ProviderError("libvirt adapteri: internetli tarmoq MVP'da o'chirilgan")
        net = ipaddress.ip_network(config.cidr)
        name = safe_id(config.name)
        xml = f"""<network>
  <name>{escape(name)}</name>
  <bridge name='{escape(("virbr-" + name[-9:]))}' stp='on' delay='0'/>
  <ip address='{config.gateway}' netmask='{net.netmask}'/>
</network>"""  # <forward> yo'q => izolyatsiyalangan tarmoq
        n = self.conn.networkDefineXML(xml)
        n.create()
        return name

    def delete_network(self, network_id: str) -> None:
        try:
            n = self.conn.networkLookupByName(safe_id(network_id))
            if n.isActive():
                n.destroy()
            n.undefine()
        except self.libvirt.libvirtError:
            pass

    def create_vm(self, config: VMConfig) -> str:
        name = safe_id(config.name)
        base = config.image  # bazaviy qcow2 yo'li (catalog'da)
        self.verify_image(base, config.checksum)
        disk = f"{self.storage_dir}/{name}.qcow2"
        pool_xml = f"""<volume><name>{escape(name)}.qcow2</name><capacity unit='G'>{max(config.disk_gb, 10)}</capacity>
<target><format type='qcow2'/></target>
<backingStore><path>{escape(base)}</path><format type='qcow2'/></backingStore></volume>"""
        pool = self.conn.storagePoolLookupByName("clpe")
        pool.createXML(pool_xml, 0)
        nics = "".join(
            f"<interface type='network'><source network='{escape(safe_id(n))}'/><model type='virtio'/></interface>"
            for n in config.networks)
        xml = f"""<domain type='kvm'>
  <name>{escape(name)}</name>
  <memory unit='MiB'>{config.ram_mb}</memory>
  <vcpu>{max(1, int(config.cpu))}</vcpu>
  <os><type arch='x86_64'>hvm</type></os>
  <devices>
    <disk type='file' device='disk'><driver name='qemu' type='qcow2'/><source file='{escape(disk)}'/><target dev='vda' bus='virtio'/></disk>
    {nics}
    <graphics type='vnc' listen='127.0.0.1' autoport='yes'/>
  </devices>
</domain>"""
        self.conn.defineXML(xml)
        return name

    def _dom(self, vm_id: str):
        try:
            return self.conn.lookupByName(safe_id(vm_id))
        except self.libvirt.libvirtError as e:
            raise ProviderError(f"VM topilmadi: {vm_id}") from e

    def start_vm(self, vm_id: str) -> None:
        self._dom(vm_id).create()

    def stop_vm(self, vm_id: str) -> None:
        self._dom(vm_id).destroy()

    def delete_vm(self, vm_id: str) -> None:
        try:
            d = self._dom(vm_id)
            if d.isActive():
                d.destroy()
            d.undefineFlags(self.libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA)
        except ProviderError:
            pass

    def create_snapshot(self, vm_id: str, name: str) -> str:
        self._dom(vm_id).snapshotCreateXML(f"<domainsnapshot><name>{escape(safe_id(name))}</name></domainsnapshot>")
        return name

    def restore_snapshot(self, vm_id: str, snapshot_id: str) -> str:
        d = self._dom(vm_id)
        d.revertToSnapshot(d.snapshotLookupByName(safe_id(snapshot_id)))
        return vm_id

    def get_vm_status(self, vm_id: str) -> str:
        try:
            state, _ = self._dom(vm_id).state()
        except ProviderError:
            return "DELETED"
        lv = self.libvirt
        return {lv.VIR_DOMAIN_RUNNING: "RUNNING", lv.VIR_DOMAIN_PAUSED: "PAUSED",
                lv.VIR_DOMAIN_SHUTOFF: "STOPPED", lv.VIR_DOMAIN_SHUTDOWN: "STOPPING"}.get(state, "ERROR")

    def get_vm_metrics(self, vm_id: str) -> VMMetrics:
        info = self._dom(vm_id).info()  # [state, maxMem KiB, mem KiB, vcpus, cpuTime ns]
        return VMMetrics(cpu_percent=0.0, ram_used_mb=info[2] / 1024, ram_limit_mb=info[1] / 1024)
