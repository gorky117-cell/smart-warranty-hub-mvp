import os
import tempfile
from pathlib import Path
import pytest

# Ensure tests use a writable SQLite database in temp
_tmp_dir = Path(tempfile.mkdtemp(prefix="swh_test_db_"))
_db_path = _tmp_dir / "app_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path.as_posix()}"
# Avoid pytest cache writes inside the repo (permission warnings)
os.environ["PYTEST_CACHE_DIR"] = str(_tmp_dir / "pytest_cache")


@pytest.fixture(scope="session", autouse=True)
def _init_test_db():
    # Import after DATABASE_URL is set
    from app.deps import init_db
    init_db()
    yield


# Tests never reach the internet unless SWH_LIVE_NETWORK_TESTS=1. Before follow-up step 3, three tests
# called the live Epson website and DNS (which has no timeout), so a slow or unreachable site could
# stall the whole run. Loopback (TestClient, local servers) is still allowed.
LIVE_NETWORK = os.getenv("SWH_LIVE_NETWORK_TESTS") == "1"


def _is_local(host) -> bool:
    host = str(host or "")
    return host in ("localhost", "::1", "testserver") or host.startswith("127.")


if not LIVE_NETWORK:
    import socket

    _real_connect = socket.socket.connect
    _real_getaddrinfo = socket.getaddrinfo

    def _guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if not _is_local(host):
            raise OSError(f"network disabled in tests: {host}")
        return _real_connect(self, address)

    def _guarded_getaddrinfo(host, *args, **kwargs):
        if host and not _is_local(host):
            raise socket.gaierror(f"network disabled in tests: {host}")
        return _real_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect = _guarded_connect
    socket.getaddrinfo = _guarded_getaddrinfo


def pytest_collection_modifyitems(config, items):
    if LIVE_NETWORK:
        return
    skip = pytest.mark.skip(reason="needs the live internet; run with SWH_LIVE_NETWORK_TESTS=1")
    for item in items:
        if "live_network" in item.keywords:
            item.add_marker(skip)
