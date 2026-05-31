"""Tests for rsID validation — M8 checklist items 1 & 2.

These tests never hit the agent; run_analysis_streaming is patched to an
immediate no-op so the endpoint returns a proper streaming response (200)
when validation passes, without touching Google APIs.
"""

import json
from unittest.mock import patch

import pytest

from tests.conftest import _fake_stream

# ── Invalid inputs → 422 Unprocessable Entity ────────────────────────────────


@pytest.mark.parametrize(
    "bad_id",
    [
        "12345",  # digits only, no rs prefix
        "rs",  # prefix with no digits
        "rs123abc",  # letters after digits
        "rsABC",  # letters instead of digits
        "",  # empty string
        "snp1051730",  # wrong prefix
        "rs 1051730",  # internal space
    ],
)
async def test_invalid_rs_id_returns_422(client, bad_id):
    response = await client.post("/api/analyze", json={"variant_id": bad_id})
    assert response.status_code == 422, f"Expected 422 for {bad_id!r}, got {response.status_code}"


# ── Valid inputs → 200 and the rsID is normalised to lowercase ────────────────


@pytest.mark.parametrize(
    "input_id, expected_id",
    [
        ("rs1051730", "rs1051730"),  # already lowercase
        ("RS1051730", "rs1051730"),  # uppercase → normalised  [checklist item 2]
        ("Rs1051730", "rs1051730"),  # mixed case → normalised
        (" rs1051730 ", "rs1051730"),  # leading/trailing spaces stripped
    ],
)
async def test_valid_rs_id_is_normalised(client, input_id, expected_id):
    with patch("src.api.main.run_analysis_streaming", side_effect=_fake_stream):
        response = await client.post("/api/analyze", json={"variant_id": input_id})

    assert response.status_code == 200, f"Expected 200 for {input_id!r}"

    # The complete event must carry the normalised rsID
    complete_events = [
        e
        for raw in response.text.split("\n\n")
        for e in [_parse_block(raw)]
        if e and e["type"] == "complete"
    ]
    assert complete_events, "No 'complete' SSE event found"
    report = complete_events[0]["data"].get("report", {})
    assert report.get("variant_id") == expected_id


def _parse_block(block: str) -> dict | None:
    block = block.strip()
    if not block:
        return None
    event_type = None
    data = None
    for line in block.splitlines():
        if line.startswith("event: "):
            event_type = line[7:].strip()
        elif line.startswith("data: "):
            try:
                data = json.loads(line[6:])
            except json.JSONDecodeError:
                data = None
    if event_type and data is not None:
        return {"type": event_type, "data": data}
    return None
