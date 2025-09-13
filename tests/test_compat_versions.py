# tests/test_compat_versions.py
from packaging.version import Version
import httpx
import starlette


def test_starlette_httpx_compat():
    """Guard against accidental version bumps that break Starlette TestClient compatibility.

    Starlette 0.36.x TestClient uses httpx.Client(app=...), which was dropped in httpx>=0.28.
    When upgrading FastAPI/Starlette, update/remove this test accordingly.
    """
    assert Version(httpx.__version__) < Version("0.28"), f"httpx {httpx.__version__} >= 0.28 breaks Starlette TestClient"
    assert Version(starlette.__version__) < Version("0.37"), f"starlette {starlette.__version__} >= 0.37 may require httpx>=0.28"