"""CORS regression tests.

The "Clear all memory" button issues a browser `fetch(DELETE /api/memory)`, which
triggers a CORS preflight. DELETE was missing from the allowed methods, so the
browser blocked it and the UI showed "Could not clear memory." These tests pin
the allowed methods so that regression can't recur silently.
"""

import pytest


async def _preflight(client, method: str):
    return await client.options(
        "/api/memory",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": method,
        },
    )


@pytest.mark.parametrize("method", ["DELETE", "GET", "POST"])
async def test_cors_preflight_allows_method(client, method):
    resp = await _preflight(client, method)
    assert resp.status_code == 200, f"Preflight for {method} failed: {resp.status_code}"
    allowed = resp.headers.get("access-control-allow-methods", "")
    assert method in allowed, f"{method} not in allow-methods: {allowed!r}"


async def test_cors_preflight_delete_specifically(client):
    """The exact request the memory-clear button makes must be permitted."""
    resp = await _preflight(client, "DELETE")
    assert resp.status_code == 200
    assert "DELETE" in resp.headers.get("access-control-allow-methods", "")
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
