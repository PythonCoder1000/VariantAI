"""Integration tests for /api/chat and /api/memory endpoints."""

import json
from unittest.mock import patch

from tests.conftest import parse_sse


async def _fake_chat_stream(variant_id, report, messages):
    yield f"event: delta\ndata: {json.dumps({'text': 'Hi '})}\n\n"
    yield f"event: delta\ndata: {json.dumps({'text': 'there'})}\n\n"
    yield f"event: done\ndata: {json.dumps({'text': 'Hi there', 'memories_added': []})}\n\n"


# ── /api/chat ────────────────────────────────────────────────────────────────


async def test_chat_streams_response(client):
    body = {
        "variant_id": "rs1051730",
        "report": {"variant_id": "rs1051730"},
        "messages": [{"role": "user", "content": "What does this mean?"}],
    }
    with patch("src.api.main.run_chat_streaming", side_effect=_fake_chat_stream):
        resp = await client.post("/api/chat", json=body)
    assert resp.status_code == 200
    events = parse_sse(resp.text)
    assert [e["type"] for e in events] == ["delta", "delta", "done"]
    assert events[-1]["data"]["text"] == "Hi there"


async def test_chat_rejects_empty_messages(client):
    body = {"variant_id": "rs1051730", "messages": []}
    resp = await client.post("/api/chat", json=body)
    assert resp.status_code == 422


async def test_chat_rejects_when_last_message_not_user(client):
    body = {
        "variant_id": "rs1051730",
        "messages": [{"role": "assistant", "content": "I spoke last"}],
    }
    resp = await client.post("/api/chat", json=body)
    assert resp.status_code == 422


async def test_chat_report_is_optional(client):
    body = {
        "variant_id": "rs1051730",
        "messages": [{"role": "user", "content": "hi"}],
    }
    with patch("src.api.main.run_chat_streaming", side_effect=_fake_chat_stream):
        resp = await client.post("/api/chat", json=body)
    assert resp.status_code == 200


# ── /api/memory ──────────────────────────────────────────────────────────────


async def test_get_memory(client):
    fake = [{"id": "1", "text": "User is a clinician", "created_at": 1.0}]
    with patch("src.api.main.memory.load_memory", return_value=fake):
        resp = await client.get("/api/memory")
    assert resp.status_code == 200
    assert resp.json() == {"items": fake}


async def test_delete_memory(client):
    with patch("src.api.main.memory.clear_memory") as mock_clear:
        resp = await client.delete("/api/memory")
    assert resp.status_code == 200
    assert resp.json() == {"status": "cleared"}
    mock_clear.assert_called_once()
