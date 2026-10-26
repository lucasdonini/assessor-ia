from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import ROUTES


def test_demo_user_registry_is_not_exposed():
    app = FastAPI()
    for router in ROUTES:
        app.include_router(router, prefix="/api")
    with TestClient(app) as client:
        assert client.get("/api/users").status_code == 404
        assert client.post("/api/users").status_code == 404
