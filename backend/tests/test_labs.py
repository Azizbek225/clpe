from app.labengine.providers import get_provider
from tests.conftest import make_student

API = "/api/v1/labs"


def test_full_lab_lifecycle_scan_topology_and_grading(client):
    h = make_student(client, "hacker1")
    r = client.post(f"{API}/network-scan-001/start", headers=h)
    assert r.status_code == 202, r.text
    st = client.get(f"{API}/network-scan-001/status", headers=h).json()
    assert st["status"] == "RUNNING"
    assert all(m["status"] == "RUNNING" for m in st["machines"])
    # "discovered" rejimi: nishon IP'lari oshkor qilinmaydi
    assert {m["name"]: bool(m["ips"]) for m in st["machines"]} == {"attacker": True, "legacy-srv": False, "web01": False}
    cidr = st["networks"][0]["cidr"]

    topo = client.get(f"{API}/network-scan-001/topology", headers=h).json()
    assert [n["id"] for n in topo["nodes"] if n["type"] == "host"] == ["host:attacker"]

    r = client.post(f"{API}/network-scan-001/scan", json={"target": "8.8.8.8", "profile": "quick"}, headers=h)
    assert r.status_code == 422  # lab tashqarisi
    r = client.post(f"{API}/network-scan-001/scan", json={"target": cidr, "profile": "services"}, headers=h)
    assert r.status_code == 200, r.text
    hosts = {x["ip"]: x for x in r.json()["hosts"]}
    assert len(hosts) == 3
    topo = r.json()["topology"]
    assert len([n for n in topo["nodes"] if n["type"] == "host"]) == 3
    assert any(e.get("blocked") for e in topo["edges"])  # internet bloklangan

    legacy = next(x for x in hosts.values() if any(p["port"] == 6667 for p in x["ports"]))
    targets = [ip for ip, x in hosts.items() if x["ports"]]
    sub = lambda body: client.post(f"{API}/network-scan-001/submit", json=body, headers=h).json()  # noqa: E731
    assert sub({"task_id": "hosts", "hosts": targets})["passed"]
    assert sub({"task_id": "ports", "ports": [p["port"] for p in legacy["ports"]]})["passed"]
    assert not sub({"task_id": "ftp-version", "value": "1.0"})["passed"]
    assert sub({"task_id": "ftp-version", "value": "2.3.4"})["passed"]
    res = sub({"task_id": "map"})
    assert res["passed"] and res["total_score"] == 100

    ev = client.get(f"{API}/network-scan-001/events", headers=h).json()
    assert {"created", "network_created", "vm_created", "scan"} <= {e["type"] for e in ev}

    machines = client.get(f"{API}/network-scan-001/machines", headers=h).json()
    assert machines[0]["metrics"]["cpu_percent"] >= 0

    assert client.post(f"{API}/network-scan-001/snapshot", json={"name": "cp1"}, headers=h).status_code == 200
    assert client.post(f"{API}/network-scan-001/reset", headers=h).status_code == 202
    assert client.get(f"{API}/network-scan-001/status", headers=h).json()["status"] == "RUNNING"
    assert client.post(f"{API}/network-scan-001/stop", headers=h).status_code == 202
    assert client.get(f"{API}/network-scan-001/status", headers=h).json()["status"] == "STOPPED"


def test_users_are_isolated(client):
    a, b = make_student(client, "iso_a"), make_student(client, "iso_b")
    ia = client.post(f"{API}/web-dvwa-sqli-001/start", headers=a).json()
    ib = client.post(f"{API}/web-dvwa-sqli-001/start", headers=b).json()
    assert ia["instance_name"] != ib["instance_name"]
    assert ia["networks"][0]["cidr"] != ib["networks"][0]["cidr"]
    # B foydalanuvchi A ning instansiyasini ko'ra olmaydi
    r = client.get(f"{API}/web-dvwa-sqli-001/status", params={"instance_id": ia["id"]}, headers=b)
    assert r.status_code == 403
    # B, A tarmog'ini skanerlay olmaydi
    r = client.post(f"{API}/web-dvwa-sqli-001/scan", json={"target": ia["networks"][0]["cidr"]}, headers=b)
    assert r.status_code == 422
    for h in (a, b):
        client.post(f"{API}/web-dvwa-sqli-001/stop", headers=h)


def test_vm_check_validator_and_reset(client):
    h = make_student(client, "pwner")
    client.post(f"{API}/exploit-vsftpd-001/start", headers=h)
    st = client.get(f"{API}/exploit-vsftpd-001/status", headers=h).json()
    r = client.post(f"{API}/exploit-vsftpd-001/submit", json={"task_id": "proof"}, headers=h).json()
    assert not r["passed"]
    # talaba exploit qilib, isbot faylini yaratdi (mock)
    from app.db import SessionLocal
    from app.models import LabMachine
    import uuid
    with SessionLocal() as db:
        target = next(db.get(LabMachine, uuid.UUID(m["id"])) for m in st["machines"] if m["name"] == "target")
        get_provider("mock").touch_file(target.vm_identifier, "/tmp/clpe_pwned")
    assert client.post(f"{API}/exploit-vsftpd-001/submit", json={"task_id": "proof"}, headers=h).json()["passed"]
    # reset — boshlang'ich snapshotga qaytadi, fayl yo'qoladi
    client.post(f"{API}/exploit-vsftpd-001/reset", headers=h)
    assert not client.post(f"{API}/exploit-vsftpd-001/submit", json={"task_id": "proof"}, headers=h).json()["passed"]
    client.post(f"{API}/exploit-vsftpd-001/stop", headers=h)


def test_blue_team_file_absent(client):
    h = make_student(client, "defender")
    client.post(f"{API}/blue-webshell-001/start", headers=h)
    st = client.get(f"{API}/blue-webshell-001/status", headers=h).json()
    assert not client.post(f"{API}/blue-webshell-001/submit", json={"task_id": "removed"}, headers=h).json()["passed"]
    from app.db import SessionLocal
    from app.models import LabMachine
    import uuid
    with SessionLocal() as db:
        m = db.get(LabMachine, uuid.UUID(st["machines"][0]["id"]))
        get_provider("mock").remove_file(m.vm_identifier, "/var/www/html/uploads/shell.php")
    assert client.post(f"{API}/blue-webshell-001/submit", json={"task_id": "removed"}, headers=h).json()["passed"]
    client.post(f"{API}/blue-webshell-001/stop", headers=h)


def test_lab_quota(client):
    h = make_student(client, "greedy")
    assert client.post(f"{API}/web-dvwa-sqli-001/start", headers=h).status_code == 202
    assert client.post(f"{API}/web-juiceshop-recon-001/start", headers=h).status_code == 202
    assert client.post(f"{API}/network-scan-001/start", headers=h).status_code == 409
    for slug in ("web-dvwa-sqli-001", "web-juiceshop-recon-001"):
        client.post(f"{API}/{slug}/stop", headers=h)


def test_nmap_import_builds_graph(client):
    h = make_student(client, "importer")
    st = client.post(f"{API}/pivot-segments-001/start", headers=h).json()
    st = client.get(f"{API}/pivot-segments-001/status", headers=h).json()
    internal = next(n["cidr"] for n in st["networks"] if n["name"] == "internal")
    ip = internal.rsplit(".", 1)[0] + ".11"
    xml = (f'<nmaprun><host><status state="up"/><address addr="{ip}" addrtype="ipv4"/><ports>'
           '<port protocol="tcp" portid="3306"><state state="open"/><service name="mysql" product="MySQL" '
           'version="5.0.51a"/></port></ports></host></nmaprun>')
    r = client.post(f"{API}/pivot-segments-001/scan/import", json={"xml": xml}, headers=h)
    assert r.status_code == 200, r.text
    labels = [n for n in r.json()["topology"]["nodes"] if n["type"] == "host" and n.get("discovered")]
    assert any(ip in n["ips"].values() for n in labels)
    assert client.post(f"{API}/pivot-segments-001/submit", json={"task_id": "internal-map"}, headers=h).json()["passed"]
    client.post(f"{API}/pivot-segments-001/stop", headers=h)


def test_admin_adds_new_lab_without_code(client, admin):
    yaml_text = """
id: custom-lab-001
title: {uz: Yangi lab}
machines:
  - {name: attacker, template: kali-linux, role: attacker}
  - {name: box, template: juice-shop}
tasks:
  - id: f
    title: Flag
    points: 50
    validation: {type: flag, flag: "CLPE{new}"}
"""
    assert client.post("/api/v1/admin/labs/validate", json={"yaml": yaml_text}, headers=admin).json()["valid"]
    bad = yaml_text.replace("tasks:", "networks:\n  - {name: lab, type: bridged}\ntasks:")
    v = client.post("/api/v1/admin/labs/validate", json={"yaml": bad}, headers=admin).json()
    assert not v["valid"] and any("bridged" in e for e in v["errors"])
    assert client.post("/api/v1/admin/labs", json={"yaml": yaml_text}, headers=admin).status_code == 201
    h = make_student(client, "newlab")
    labs = [x["id"] for x in client.get(API, headers=h).json()]
    assert "custom-lab-001" in labs
    detail = client.get(f"{API}/custom-lab-001", headers=h).json()
    assert "flag_hash" not in str(detail)
    client.post(f"{API}/custom-lab-001/start", headers=h)
    assert client.post(f"{API}/custom-lab-001/submit", json={"task_id": "f", "value": "CLPE{new}"}, headers=h).json()["passed"]
    client.post(f"{API}/custom-lab-001/stop", headers=h)
    # student manifest yoza olmaydi
    assert client.post("/api/v1/admin/labs", json={"yaml": yaml_text}, headers=h).status_code == 403
