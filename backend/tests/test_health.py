"""Tests for the /api/health endpoint."""


async def test_health_returns_ok(client):
    response = await client.get("/api/health")
    assert response.status_code == 200


async def test_health_body(client):
    body = (await client.get("/api/health")).json()
    assert body["status"] == "ok"
    assert "version" in body
