import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app import models  # noqa: F401  (registers tables on Base)
from app.api.routes import router
from app.api.candidate_routes import router as candidate_router
from app.api.suggest_routes import router as suggest_router
from app.api.content_routes import router as content_router
from app.api.tracking_routes import router as tracking_router


@pytest.fixture()
def client():
    """A TestClient backed by a fresh in-memory database for every test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.include_router(candidate_router, prefix="/api/v1")
    app.include_router(suggest_router, prefix="/api/v1")
    app.include_router(content_router, prefix="/api/v1")
    app.include_router(tracking_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c
