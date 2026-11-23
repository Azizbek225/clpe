def test_register_login_me(client):
    r = client.post("/api/v1/auth/register", json={"username": "ali", "email": "ali@test.uz", "password": "Secret123!"})
    assert r.status_code == 201
    assert r.json()["roles"] == ["student"]
    r = client.post("/api/v1/auth/login", json={"login": "ali@test.uz", "password": "Secret123!"})
    tok = r.json()
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok['access_token']}"}).json()
    assert me["username"] == "ali" and "labs:use" in me["permissions"]
    assert client.post("/api/v1/auth/login", json={"login": "ali", "password": "wrong-pass"}).status_code == 401


def test_refresh_rotation_and_reuse_detection(client):
    client.post("/api/v1/auth/register", json={"username": "vali", "email": "vali@test.uz", "password": "Secret123!"})
    t1 = client.post("/api/v1/auth/login", json={"login": "vali", "password": "Secret123!"}).json()
    t2 = client.post("/api/v1/auth/refresh", json={"refresh_token": t1["refresh_token"]})
    assert t2.status_code == 200
    # eski tokenni qayta ishlatish -> butun oila bekor qilinadi
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": t1["refresh_token"]}).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": t2.json()["refresh_token"]}).status_code == 401


def test_rbac_student_cannot_edit(client, student):
    assert client.post("/api/v1/courses", json={"slug": "x", "title": "x"}, headers=student).status_code == 403
    assert client.get("/api/v1/admin/users", headers=student).status_code == 403
    assert client.get("/api/v1/courses").status_code == 401
