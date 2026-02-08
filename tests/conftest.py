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
