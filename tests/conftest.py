import subprocess
import sys

import pytest

from recommender.config import DB_PATH, ROOT_DIR


@pytest.fixture(scope="session", autouse=True)
def database():
    """Build the SQLite DB once if it doesn't exist, so tests work on a fresh clone."""
    if not DB_PATH.exists():
        subprocess.run([sys.executable, str(ROOT_DIR / "db" / "loader.py")], check=True)
