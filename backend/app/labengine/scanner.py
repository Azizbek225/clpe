"""Tarmoq skaneri va topologiya quruvchi.

Skan laboratoriyaning HUJUMCHI mashinasi ichida bajariladi (host'da emas). Buyruq oq ro'yxatdagi
profildan quriladi, nishon esa laboratoriya tarmog'i ichida ekanligi tekshiriladi.
Talaba o'z terminalida olgan `nmap -oX` natijasini import qilishi ham mumkin.
"""
from __future__ import annotations

import ipaddress
from typing import Any

from defusedxml import ElementTree as ET

SCAN_PROFILES: dict[str, list[str]] = {
    "ping": ["-sn", "-T4"],
    "quick": ["-T4", "-F", "--open"],
    "services": ["-sV", "-T4", "--top-ports", "1000", "--open"],
    "full": ["-T4", "-p-", "--open"],
}


class ScanError(ValueError):
    pass


def validate_target(target: str, allowed_cidrs: list[str]) -> str:
    try:
        net = ipaddress.ip_network(target.strip(), strict=False)
    except ValueError as e:
        raise ScanError("Nishon IP yoki CIDR ko'rinishida bo'lishi kerak") from e
    for cidr in allowed_cidrs:
        if net.subnet_of(ipaddress.ip_network(cidr)):
            return str(net) if net.num_addresses > 1 else str(net.network_address)
    raise ScanError("Nishon laboratoriya tarmog'idan tashqarida — skan rad etildi")


def build_nmap_argv(profile: str, target: str) -> list[str]:
    if profile not in SCAN_PROFILES:
        raise ScanError(f"Noma'lum skan profili: {profile}")
    return ["nmap", "-oX", "-", *SCAN_PROFILES[profile], target]


def parse_nmap_xml(xml: str, allowed_cidrs: list[str] | None = None) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml)
    except Exception as e:
        raise ScanError("nmap XML'ni o'qib bo'lmadi") from e
    nets = [ipaddress.ip_network(c) for c in (allowed_cidrs or [])]
    hosts = []
    for h in root.findall("host"):
        st = h.find("status")
        if st is not None and st.get("state") != "up":
            continue
        ip = mac = vendor = None
        for a in h.findall("address"):
            if a.get("addrtype") == "ipv4":
                ip = a.get("addr")
            elif a.get("addrtype") == "mac":
                mac, vendor = a.get("addr"), a.get("vendor")
        if not ip:
            continue
        if nets and not any(ipaddress.ip_address(ip) in n for n in nets):
            continue  # lab tashqarisidagi natijalar e'tiborsiz qoldiriladi
        hn = h.find("hostnames/hostname")
        osm = h.find("os/osmatch")
        ports = []
        for p in h.findall("ports/port"):
            state = p.find("state")
            if state is None or state.get("state") != "open":
                continue
            svc = p.find("service")
            ports.append({
                "port": int(p.get("portid", 0)), "protocol": p.get("protocol", "tcp"),
                "service": svc.get("name", "") if svc is not None else "",
                "product": svc.get("product", "") if svc is not None else "",
                "version": svc.get("version", "") if svc is not None else "",
            })
        hosts.append({"ip": ip, "hostname": hn.get("name") if hn is not None else None, "mac": mac,
                      "vendor": vendor, "os": osm.get("name") if osm is not None else None,
                      "ports": sorted(ports, key=lambda x: x["port"])})
    return hosts


def merge_hosts(scans: list[list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    """Bir nechta skan natijasini IP bo'yicha birlashtiradi (keyingisi ustun)."""
    merged: dict[str, dict[str, Any]] = {}
    for hosts in scans:
        for h in hosts:
            cur = merged.setdefault(h["ip"], {"ip": h["ip"], "ports": {}})
            for k in ("hostname", "mac", "vendor", "os"):
                if h.get(k):
                    cur[k] = h[k]
            for p in h.get("ports", []):
                key = f'{p["port"]}/{p["protocol"]}'
                old = cur["ports"].get(key, {})
                cur["ports"][key] = {**old, **{k: v for k, v in p.items() if v}}
    for h in merged.values():
        h["ports"] = sorted(h["ports"].values(), key=lambda x: x["port"])
    return merged


def build_topology(instance, scans: list[list[dict[str, Any]]], reveal: str = "discovered") -> dict[str, Any]:
    """Graf: tarmoq tugunlari + host tugunlari + bog'lanishlar. Front-end shu JSON'ni chizadi."""
    discovered = merge_hosts(scans)
    nodes: list[dict[str, Any]] = [{
        "id": "internet", "type": "internet", "label": "Internet",
        "blocked": not any(n.isolation_policy == "internet" for n in instance.networks),
    }]
    edges: list[dict[str, Any]] = []
    for n in instance.networks:
        nodes.append({"id": f"net:{n.network_name}", "type": "network", "label": n.network_name, "cidr": n.cidr,
                      "policy": n.isolation_policy})
        edges.append({"source": f"net:{n.network_name}", "target": "internet",
                      "blocked": n.isolation_policy != "internet"})
    seen_ips: set[str] = set()
    for m in instance.machines:
        ips = m.ip_addresses or {}
        found = [discovered[ip] for ip in ips.values() if ip in discovered]
        visible = reveal == "full" or m.role == "attacker" or bool(found)
        if not visible:
            continue
        info = found[0] if found else {}
        seen_ips.update(ips.values())
        is_known = reveal == "full" or m.role == "attacker"
        nodes.append({
            "id": f"host:{m.name}", "type": "host", "role": m.role if is_known else "unknown",
            "label": m.name if is_known else (info.get("hostname") or next(iter(ips.values()), "?")),
            "ips": ips, "os": info.get("os") or (m.operating_system if is_known else None),
            "status": m.status, "ports": info.get("ports", []), "discovered": bool(found), "you": m.role == "attacker",
        })
        for net_name in ips:
            edges.append({"source": f"host:{m.name}", "target": f"net:{net_name}"})
    # Skan topgan, lekin lab mashinalariga mos kelmagan IP'lar (masalan gateway)
    for ip, h in discovered.items():
        if ip in seen_ips:
            continue
        net = next((n for n in instance.networks if ipaddress.ip_address(ip) in ipaddress.ip_network(n.cidr)), None)
        nodes.append({"id": f"ip:{ip}", "type": "host", "role": "unknown", "label": h.get("hostname") or ip,
                      "ips": {net.network_name if net else "?": ip}, "os": h.get("os"), "ports": h["ports"],
                      "discovered": True})
        if net:
            edges.append({"source": f"ip:{ip}", "target": f"net:{net.network_name}"})
    return {"nodes": nodes, "edges": edges, "discovered_hosts": len(discovered)}
