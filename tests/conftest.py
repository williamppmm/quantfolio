import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.main import app


@pytest.fixture()
def client() -> TestClient:
    """FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client
