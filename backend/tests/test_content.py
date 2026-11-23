from tests.conftest import make_student


def test_module_and_lesson_editing(client, admin):
    course = client.get("/api/v1/courses/networking-fundamentals", headers=admin).json()
    mid = course["modules_detail"][0]["id"]
    r = client.put(f"/api/v1/modules/{mid}", json={"title": "Yangilangan modul"}, headers=admin)
    assert r.status_code == 200
    r = client.post("/api/v1/lessons", json={"module_id": mid, "title": "Yangi dars", "content": "# Salom",
                                             "translations": {"en": {"title": "New lesson", "content": "# Hi"}}},
                    headers=admin)
    lid = r.json()["id"]
    assert client.get(f"/api/v1/lessons/{lid}?lang=en", headers=admin).json()["title"] == "New lesson"
    assert client.get(f"/api/v1/lessons/{lid}?lang=uz", headers=admin).json()["content"] == "# Salom"
    pack = client.get("/api/v1/courses/networking-fundamentals/export", headers=admin).text
    assert "Yangilangan modul" in pack and "Yangi dars" in pack
    client.delete(f"/api/v1/lessons/{lid}", headers=admin)


def test_quiz_progress_and_certificate(client):
    h = make_student(client, "learner")
    c = client.get("/api/v1/courses/ethical-hacking", headers=h).json()
    for m in c["modules_detail"]:
        for le in m["lessons"]:
            client.post(f"/api/v1/lessons/{le['id']}/complete", headers=h)
    qid = c["modules_detail"][0]["quiz"]["id"]
    quiz = client.post(f"/api/v1/quizzes/{qid}/start", headers=h).json()
    wrong = {q["id"]: [q["options"][-1]["id"]] for q in quiz["questions"]}
    r = client.post(f"/api/v1/quizzes/{qid}/submit", json={"answers": wrong}, headers=h).json()
    assert not r["passed"]
    right = {x["question_id"]: x["correct_options"] for x in r["review"]}
    r = client.post(f"/api/v1/quizzes/{qid}/submit", json={"answers": right}, headers=h).json()
    assert r["passed"] and r["certificate"]
    code = r["certificate"]["verification_code"]
    assert client.get(f"/api/v1/certificates/verify/{code}").json()["valid"]
    me = client.get("/api/v1/progress", headers=h).json()
    assert me["xp"] > 0


def test_ctf(client):
    h = make_student(client, "ctfer")
    chs = client.get("/api/v1/ctf/challenges", headers=h).json()
    b64 = next(c for c in chs if c["title"] == "Base64 sirlari")
    assert not client.post(f"/api/v1/ctf/challenges/{b64['id']}/submit", json={"flag": "CLPE{no}"}, headers=h).json()["correct"]
    assert client.post(f"/api/v1/ctf/challenges/{b64['id']}/submit",
                       json={"flag": "CLPE{b453_64_is_not_encryption}"}, headers=h).json()["correct"]
    board = client.get("/api/v1/ctf/leaderboard", headers=h).json()
    assert board[0]["username"] == "ctfer"
