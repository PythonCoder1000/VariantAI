"""Unit tests for _check_variant_exists — the dbSNP pre-flight not-found check.

The previous implementation hit a dead dbSNP beta endpoint that returned HTTP 404
for *every* rsID, so every variant was wrongly flagged "unknown". These tests pin
the corrected behaviour: only an explicit ``count == "0"`` from NCBI esearch marks
a variant as not-found; everything else fails open (returns True).
"""

from unittest.mock import MagicMock, patch

from src.agent.managed_agent import _check_variant_exists


def _mock_response(status_code: int, count: str | None):
    resp = MagicMock()
    resp.status_code = status_code
    body: dict = {"esearchresult": {}}
    if count is not None:
        body["esearchresult"]["count"] = count
    resp.json.return_value = body
    return resp


def test_existing_variant_returns_true():
    with patch("src.agent.managed_agent.httpx.get", return_value=_mock_response(200, "1")):
        assert _check_variant_exists("rs1051730") is True


def test_nonexistent_variant_returns_false():
    with patch("src.agent.managed_agent.httpx.get", return_value=_mock_response(200, "0")):
        assert _check_variant_exists("rs999999999999") is False


def test_http_error_fails_open():
    with patch("src.agent.managed_agent.httpx.get", return_value=_mock_response(500, None)):
        assert _check_variant_exists("rs1051730") is True


def test_network_exception_fails_open():
    with patch("src.agent.managed_agent.httpx.get", side_effect=Exception("timeout")):
        assert _check_variant_exists("rs1051730") is True


def test_malformed_response_fails_open():
    # No "count" key at all → count is None → not equal to "0" → True (fail open)
    with patch("src.agent.managed_agent.httpx.get", return_value=_mock_response(200, None)):
        assert _check_variant_exists("rs1051730") is True


def test_non_numeric_rsid_fails_open_without_request():
    # Guard clause: never issue a request for a malformed rs number.
    with patch("src.agent.managed_agent.httpx.get") as mock_get:
        assert _check_variant_exists("rsABC") is True
        mock_get.assert_not_called()
