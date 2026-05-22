"""Tests for the auth API \u2014 signup, login, JWT decode, and user_id isolation."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api import auth as auth_api
from backend.database import Base, get_db
from backend.models.user import User, ensure_users_table
from backend.services import auth_service


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine, tables=[User.__table__])
    ensure_users_table(engine)

    app = FastAPI()
    app.include_router(auth_api.router, prefix="/api/auth")

    def _override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    yield TestClient(app)


SIGNUP = {
    "email": "seller@example.com",
    "password": "supersecret123",
    "business_name": "Sunova Herbal",
    "platform": "flipkart",
    "monthly_revenue_range": "10L-50L",
}


class TestSignup:
    def test_creates_user_and_returns_token(self, client):
        res = client.post("/api/auth/signup", json=SIGNUP)
        assert res.status_code == 200
        body = res.json()
        assert body["token"]
        assert body["user"]["email"] == "seller@example.com"
        assert body["user"]["business_name"] == "Sunova Herbal"
        assert body["user"]["auth_provider"] == "email"
        assert body["user"]["is_new_user"] is True

        # JWT round-trip works
        payload = auth_service.decode_token(body["token"])
        assert payload["user_id"] == body["user"]["id"]
        assert payload["email"] == body["user"]["email"]

    def test_password_is_bcrypt_hashed(self, client):
        client.post("/api/auth/signup", json=SIGNUP)
        # Re-query via /me using the token, then verify password hash
        token = client.post("/api/auth/login", json={
            "email": SIGNUP["email"], "password": SIGNUP["password"]
        }).json()["token"]
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
        assert me["email"] == SIGNUP["email"]

    def test_duplicate_email_rejected(self, client):
        assert client.post("/api/auth/signup", json=SIGNUP).status_code == 200
        res = client.post("/api/auth/signup", json=SIGNUP)
        assert res.status_code == 400


class TestLogin:
    def test_valid_credentials_returns_token(self, client):
        client.post("/api/auth/signup", json=SIGNUP)
        res = client.post("/api/auth/login", json={
            "email": SIGNUP["email"], "password": SIGNUP["password"]
        })
        assert res.status_code == 200
        assert res.json()["token"]

    def test_wrong_password_rejected(self, client):
        client.post("/api/auth/signup", json=SIGNUP)
        res = client.post("/api/auth/login", json={
            "email": SIGNUP["email"], "password": "wrongpass1"
        })
        assert res.status_code == 401

    def test_unknown_email_rejected(self, client):
        res = client.post("/api/auth/login", json={
            "email": "nobody@example.com", "password": "whatever1"
        })
        assert res.status_code == 401

    def test_microsoft_account_cannot_password_login(self, client):
        # Seed a Microsoft-linked user directly
        from backend.database import SessionLocal  # noqa: WPS433
        # Use the overridden Session for this test app instead
        for db in client.app.dependency_overrides[get_db]():
            u = User(
                email="ms@example.com",
                auth_provider="microsoft",
                microsoft_id="ms-id-1",
            )
            db.add(u)
            db.commit()
            break

        res = client.post("/api/auth/login", json={
            "email": "ms@example.com", "password": "doesntmatter1"
        })
        assert res.status_code == 400
        assert "Microsoft login" in res.json()["detail"]


class TestProtectedEndpoint:
    def test_me_requires_token(self, client):
        assert client.get("/api/auth/me").status_code == 401

    def test_me_rejects_bogus_token(self, client):
        res = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
        assert res.status_code == 401

    def test_me_returns_authenticated_user(self, client):
        token = client.post("/api/auth/signup", json=SIGNUP).json()["token"]
        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.json()["email"] == SIGNUP["email"]


class TestPasswordHashing:
    def test_hash_and_verify(self):
        h = auth_service.hash_password("hunter22-secret")
        assert h != "hunter22-secret"
        assert auth_service.verify_password("hunter22-secret", h) is True
        assert auth_service.verify_password("wrong", h) is False
        assert auth_service.verify_password("x", None) is False
