"""Haqiqiy Docker bilan uchdan-uchgacha sinov (CI'da yoki lokal):

    CLPE_E2E_ATTACKER_IMAGE=instrumentisto/nmap:latest python scripts/e2e_docker.py

Tekshiradi: izolyatsiyalangan tarmoq yaratiladi (internal=True), nishon konteyner ishga tushadi,
nmap HUJUMCHI konteyner ichida bajariladi, topologiya quriladi, port_discovery baholanadi,
nishondan internetga chiqib bo'lmaydi, to'xtatilgach barcha konteyner/tarmoqlar o'chiriladi.
"""
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
tmp = Path(tempfile.mkdtemp())
attacker_image = os.environ.get("CLPE_E2E_ATTACKER_IMAGE", "clpe/attacker:1.0")
(tmp / "catalog.yaml").write_text(f"""
templates:
  kali-linux:
    name: attacker
    operating_system: Linux
    image_reference: {attacker_image}
    virtualization_provider: docker
    role: attacker
    default_cpu: 0.5
    default_ram: 256
    meta: {{entrypoint: ["sleep"], command: ["infinity"], cap_add: [NET_RAW], shell: /bin/sh}}
  juice-shop:
    name: Juice Shop
    operating_system: Node.js
    image_reference: bkimminich/juice-shop:latest
    virtualization_provider: docker
    role: target
    default_cpu: 1
    default_ram: 768
    meta: {{tty: false, mock_ports: [{{port: 3000, service: http}}]}}
""")
labs = tmp / "labs"
labs.mkdir()
(labs / "e2e.yaml").write_text("""
id: e2e-juice
title: E2E
machines:
  - {name: attacker, template: kali-linux, role: attacker}
  - {name: shop, template: juice-shop}
networks: [{name: lab, type: isolated}]
tasks:
  - {id: port, title: port, points: 10, validation: {type: port_discovery, machine: shop}}
""")
(tmp / "content").mkdir()
for f in ("catalog.yaml", "glossary.yaml", "ctf.yaml"):
    (tmp / "content" / f).write_text((ROOT / "content" / f).read_text())
os.environ.update(CLPE_DATABASE_URL=f"sqlite:///{tmp}/e2e.db", CLPE_LAB_PROVIDER="docker",
                  CLPE_CATALOG_FILE=str(tmp / "catalog.yaml"), CLPE_LABS_DIR=str(labs),
                  CLPE_CONTENT_DIR=str(tmp / "content"))

import docker  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def check(cond, msg):
    print(("✔ " if cond else "✖ ") + msg)
    if not cond:
        sys.exit(1)


dk = docker.from_env()
with TestClient(app) as c:
    c.post("/api/v1/auth/register", json={"username": "e2e", "email": "e2e@x.uz", "password": "Secret123!"})
    tok = c.post("/api/v1/auth/login", json={"login": "e2e", "password": "Secret123!"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    r = c.post("/api/v1/labs/e2e-juice/start", headers=h)
    st = c.get("/api/v1/labs/e2e-juice/status", headers=h).json()
    check(st["status"] == "RUNNING", f"lab RUNNING ({st['status']} {st.get('error')})")
    name = st["instance_name"]
    net = dk.networks.get(f"{name}-lab")
    check(net.attrs["Internal"] is True, f"docker tarmog'i internal=True ({net.name}, {st['networks'][0]['cidr']})")
    conts = dk.containers.list(filters={"label": f"clpe.instance={name}"})
    check(len(conts) == 2, "2 ta konteyner ishlayapti")
    check(all(not ct.attrs["HostConfig"]["Privileged"] and not ct.attrs["HostConfig"]["PortBindings"] for ct in conts),
          "privileged=False, host'ga port ochilmagan")
    shop = next(ct for ct in conts if ct.labels["clpe.machine"] == "shop")
    ip = list(shop.attrs["NetworkSettings"]["Networks"].values())[0]["IPAddress"]
    for _ in range(30):  # Juice Shop ishga tushishini kutish
        res = c.post("/api/v1/labs/e2e-juice/scan", json={"target": ip, "profile": "quick"}, headers=h)
        if res.status_code == 200 and any(p["port"] == 3000 for hst in res.json()["hosts"] for p in hst["ports"]):
            break
        time.sleep(3)
    check(res.status_code == 200, f"nmap hujumchi konteyner ichida bajarildi ({res.status_code})")
    ports = [p["port"] for hst in res.json()["hosts"] for p in hst["ports"]]
    check(3000 in ports, f"nishon porti topildi: {ports}")
    topo = res.json()["topology"]
    check(any(n.get("discovered") and n["type"] == "host" and n.get("role") != "attacker" for n in topo["nodes"]),
          "topologiya grafigida nishon paydo bo'ldi")
    out = c.post("/api/v1/labs/e2e-juice/scan", json={"target": "8.8.8.8"}, headers=h)
    check(out.status_code == 422, "lab tashqarisini skanerlash rad etildi")
    attacker = next(ct for ct in conts if ct.labels["clpe.machine"] == "attacker")
    egress = attacker.exec_run(["sh", "-c", "wget -q -T 4 -O- http://1.1.1.1 >/dev/null 2>&1 && echo OPEN || echo BLOCKED"])
    check(b"BLOCKED" in egress.output, f"lab tarmog'idan internetga chiqish yopiq ({egress.output.strip()[:40]!r})")
    sub = c.post("/api/v1/labs/e2e-juice/submit", json={"task_id": "port", "ports": [3000]}, headers=h).json()
    check(sub["passed"], f"port_discovery baholandi: {sub['feedback']}")
    mid = next(m["id"] for m in c.get("/api/v1/labs/e2e-juice/machines", headers=h).json() if m["name"] == "attacker")
    with c.websocket_connect(f"/ws/console/{mid}?token={tok}") as ws:
        ws.send_text('{"type": "input", "data": "echo CLPE_$((40+2)) && hostname\\n"}')
        buf = b""
        for _ in range(20):
            buf += ws.receive_bytes()
            if b"CLPE_42" in buf and b"attacker" in buf.split(b"CLPE_42", 1)[1]:
                break
    check(b"CLPE_42" in buf, "brauzer terminali lab konteyneri ichida ishlaydi (hostname=attacker)")
    snap = c.post("/api/v1/labs/e2e-juice/snapshot", json={"name": "cp1"}, headers=h)
    check(snap.status_code == 200, "snapshot olindi (docker commit)")
    c.post("/api/v1/labs/e2e-juice/stop", headers=h)
    st = c.get("/api/v1/labs/e2e-juice/status", headers=h).json()
    check(st["status"] == "STOPPED", "lab to'xtatildi")
    left = dk.containers.list(all=True, filters={"label": f"clpe.instance={name}"})
    nets = dk.networks.list(names=[f"{name}-lab"])
    check(not left and not nets, "barcha konteyner va tarmoqlar tozalandi")
print("E2E OK")
