# tests/test_compat_versions.py
from packaging.version import Version
import httpx, starlette, pytest


def test_starlette_httpx_compat():
    h = Version(httpx.__version__)
    s = Version(starlette.__version__)
    # Only enforce httpx<0.28 for older Starlette where Client(app=...) breaks
    if s < Version("0.47"):
        assert h < Version("0.28"), (
            "httpx>=0.28 breaks older Starlette TestClient (Client(app=...))"
        )
    else:
        pytest.skip("Compat check applies only to Starlette<0.47; on newer Starlette it's just a deprecation.")
