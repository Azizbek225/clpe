import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ.setdefault("CLPE_DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ["CLPE_LAB_PROVIDER"] = "mock"
os.environ["CLPE_USE_CELERY"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def _login(client, login, password):
    r = client.post("/api/v1/auth/login", json={"login": login, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin(client):
    return _login(client, "admin", "Admin12345!")


def make_student(client, name):
    client.post("/api/v1/auth/register", json={"username": name, "email": f"{name}@test.uz", "password": "Secret123!"})
    return _login(client, name, "Secret123!")


@pytest.fixture
def student(client, request):
    return make_student(client, f"st_{request.node.name[:40]}")
