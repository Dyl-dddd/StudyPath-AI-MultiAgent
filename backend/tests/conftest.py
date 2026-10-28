import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["JWT_SECRET"] = "test-only-secret-never-used-outside-pytest"
from app.core.db import Base, get_db
from app.api import auth as auth_api
from app.main import app

@asynccontextmanager
async def _test_lifespan(_app):
    yield


app.router.lifespan_context = _test_lifespan


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database = tmp_path / "test.sqlite"
    engine = create_engine(f"sqlite:///{database.as_posix()}", connect_args={"check_same_thread": False})
    testing_sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_db():
        db = testing_sessions()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    # Route tests focus on post-registration behavior. Captcha challenge validation
    # has its own production boundary and is bypassed in this fixture.
    monkeypatch.setattr(auth_api, "_consume_registration_captcha", lambda *_args: None)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()
