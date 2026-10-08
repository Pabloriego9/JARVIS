import pytest
from fastapi.testclient import TestClient
from jarvis.app import create_app
from jarvis.config import Settings


@pytest.fixture
def app(tmp_path):
    return create_app(Settings(data_dir=tmp_path / "data", api_key=""))


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        token = (app.state.settings.data_dir / "admin.token").read_text()
        client.headers["Authorization"] = f"Bearer {token}"
        yield client
