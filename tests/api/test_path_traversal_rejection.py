from fastapi.testclient import TestClient

from loquilex.api.server import app


def test_storage_info_traversal_rejected():
    client = TestClient(app)
    # Provide suspicious traversal-ish path; server should return generic 400
    r = client.get("/storage/info", params={"path": "../.."})
    assert r.status_code == 400
    detail = r.json().get("detail", "")
    assert detail == "Cannot access path"
