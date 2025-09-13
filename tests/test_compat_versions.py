# tests/test_compat_versions.py
from packaging.version import Version
import httpx
import starlette


def test_starlette_httpx_compat():
    assert Version(httpx.__version__) < Version(
        "0.28"
    ), "httpx>=0.28 breaks Starlette 0.36.x TestClient (Client(app=...))"
    assert Version(starlette.__version__) < Version("0.37")
