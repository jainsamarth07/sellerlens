"""Tests for persisted chat-session CRUD."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api import chat_sessions as chat_sessions_api
from backend.database import Base, get_db
from backend.models.chat import ChatMessage, ChatSession, ensure_chat_tables
from backend.services.auth_service import current_user_id


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(
        bind=engine, tables=[ChatSession.__table__, ChatMessage.__table__]
    )
    ensure_chat_tables(engine)

    app = FastAPI()
    app.include_router(chat_sessions_api.router, prefix="/api/chat")

    def _override():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    # Default authenticated user for the bulk of the tests; individual tests
    # can override by re-patching ``app.dependency_overrides[current_user_id]``.
    current_user = {"id": "1"}
    app.dependency_overrides[get_db] = _override
    app.dependency_overrides[current_user_id] = lambda: current_user["id"]
    app.state.current_user = current_user
    yield app, TestClient(app)


class TestChatSessionsAPI:
    def test_create_and_list_session(self, client):
        _app, c = client
        res = c.post(
            "/api/chat/sessions",
            json={"label": "April 2026", "period": "2026-04"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["label"] == "April 2026"
        assert body["settlement_period"] == "2026-04"
        assert body["message_count"] == 0
        sid = body["id"]

        listing = c.get("/api/chat/sessions").json()
        assert any(s["id"] == sid for s in listing)

    def test_add_and_fetch_messages(self, client):
        _app, c = client
        sid = c.post("/api/chat/sessions", json={"label": "x"}).json()["id"]

        r1 = c.post(
            f"/api/chat/sessions/{sid}/messages",
            json={"role": "user", "content": "Hello"},
        )
        assert r1.status_code == 200
        r2 = c.post(
            f"/api/chat/sessions/{sid}/messages",
            json={"role": "assistant", "content": "Hi there"},
        )
        assert r2.status_code == 200

        msgs = c.get(f"/api/chat/sessions/{sid}/messages").json()
        assert [m["role"] for m in msgs] == ["user", "assistant"]
        assert [m["content"] for m in msgs] == ["Hello", "Hi there"]

    def test_delete_session_cascades_messages(self, client):
        _app, c = client
        sid = c.post("/api/chat/sessions", json={"label": "x"}).json()["id"]
        c.post(
            f"/api/chat/sessions/{sid}/messages",
            json={"role": "user", "content": "ping"},
        )

        res = c.delete(f"/api/chat/sessions/{sid}")
        assert res.status_code == 200
        assert c.get(f"/api/chat/sessions/{sid}/messages").status_code == 404
        listing = c.get("/api/chat/sessions").json()
        assert all(s["id"] != sid for s in listing)

    def test_unknown_session_404(self, client):
        _app, c = client
        assert c.get("/api/chat/sessions/nope/messages").status_code == 404
        assert c.delete("/api/chat/sessions/nope").status_code == 404

    def test_isolated_user_scope(self, client):
        app, c = client
        # Alice creates a session
        app.state.current_user["id"] = "alice"
        sid = c.post("/api/chat/sessions", json={"label": "mine"}).json()["id"]

        # Bob cannot see / mutate Alice's session
        app.state.current_user["id"] = "bob"
        assert c.get(f"/api/chat/sessions/{sid}/messages").status_code == 404
        assert all(s["id"] != sid for s in c.get("/api/chat/sessions").json())

        # Alice still owns it
        app.state.current_user["id"] = "alice"
        assert any(s["id"] == sid for s in c.get("/api/chat/sessions").json())
