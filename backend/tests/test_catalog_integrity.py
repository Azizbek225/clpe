"""Kontent yaxlitligi: barcha lab manifestlari yuklanadi, kurs/CTF havolalari mavjud labga ishora qiladi,
har bir lab mock provayderda ishga tushadi va to'xtaydi."""
import pytest
import yaml

from app.config import get_settings
from tests.conftest import make_student

S = get_settings()
LAB_FILES = sorted(S.labs_dir.glob("*.yaml"))
LAB_IDS = {yaml.safe_load(p.read_text())["id"] for p in LAB_FILES}


def test_all_manifests_loaded(client, admin):
    loaded = {x["slug"] for x in client.get("/api/v1/admin/labs", headers=admin).json()}
    assert LAB_IDS <= loaded
    assert len(LAB_IDS) >= 18


def test_course_and_ctf_lab_links_exist():
    for p in (S.content_dir / "courses").glob("*.yaml"):
        for m in yaml.safe_load(p.read_text())["modules"]:
            for le in m["lessons"]:
                if le.get("lab"):
                    assert le["lab"] in LAB_IDS, f"{p.name}: {le['lab']}"
            for q in (m.get("quiz") or {}).get("questions", []):
                assert q["correct"] and all(i < len(q["options"]) for i in q["correct"]), q["q"]
    ctf = yaml.safe_load((S.content_dir / "ctf.yaml").read_text())
    chs = [c for e in ctf["events"] for c in e["challenges"]]
    assert len(chs) >= 20
    for c in chs:
        if c.get("lab_slug"):
            assert c["lab_slug"] in LAB_IDS


@pytest.mark.parametrize("lab_id", sorted(LAB_IDS))
def test_every_lab_starts_and_stops(client, lab_id):
    h = make_student(client, f"run_{lab_id[:30]}")
    assert client.post(f"/api/v1/labs/{lab_id}/start", headers=h).status_code == 202
    st = client.get(f"/api/v1/labs/{lab_id}/status", headers=h).json()
    assert st["status"] == "RUNNING", st
    client.post(f"/api/v1/labs/{lab_id}/stop", headers=h)
    assert client.get(f"/api/v1/labs/{lab_id}/status", headers=h).json()["status"] == "STOPPED"
