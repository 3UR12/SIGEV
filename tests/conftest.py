from __future__ import annotations

import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    database = tmp_path / "sigev-test.sqlite3"
    application = create_app(
        {"TESTING": True, "DATABASE": str(database), "SECRET_KEY": "pruebas-sigev"}
    )
    yield application


@pytest.fixture
def client(app):
    return app.test_client()
