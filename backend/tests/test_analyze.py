"""Integration tests for /api/analyze — M8 checklist items 3-10.

The Google Managed Agent is mocked; this validates the SSE contract,
report shape, and confidence enum without live API calls.
"""

import json
from unittest.mock import patch

import pytest

from tests.conftest import (
    PROGRESS_KEYWORDS,
    _fake_stream,
    parse_sse,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _analyze(client, rs_id: str, stream=_fake_stream) -> list[dict]:
    """POST /api/analyze and return parsed SSE events."""
    with patch("src.api.main.run_analysis_streaming", side_effect=stream):
        response = await client.post("/api/analyze", json={"variant_id": rs_id})
    assert response.status_code == 200
    return parse_sse(response.text)


# ── SSE stream structure ──────────────────────────────────────────────────────


async def test_sse_has_progress_events(client):
    events = await _analyze(client, "rs1051730")
    progress = [e for e in events if e["type"] == "progress"]
    assert len(progress) >= 7, f"Expected ≥7 progress events, got {len(progress)}"


async def test_seven_database_keywords_present(client):
    """All 7 database names appear in progress text before complete fires."""
    events = await _analyze(client, "rs1051730")
    progress_text = " ".join(
        e["data"].get("text", "").lower() for e in events if e["type"] == "progress"
    )
    for kw in PROGRESS_KEYWORDS:
        assert kw in progress_text, f"Expected keyword '{kw}' in progress events"


async def test_complete_event_comes_last(client):
    events = await _analyze(client, "rs1051730")
    complete = [e for e in events if e["type"] == "complete"]
    assert complete, "No 'complete' event found"
    assert events[-1]["type"] == "complete", "complete event must be last"


# ── Report shape (checklist items 5-6) ───────────────────────────────────────

REQUIRED_SECTIONS = [
    "clinical_risk",
    "gene_function",
    "structural_impact",
    "research_summary",
    "bottom_line",
]

VALID_CONFIDENCE = {"high", "medium", "low"}


async def test_report_has_all_five_sections(client):
    events = await _analyze(client, "rs1051730")
    complete = next(e for e in events if e["type"] == "complete")
    report = complete["data"]["report"]
    assert report is not None, "report must not be None"
    for section in REQUIRED_SECTIONS:
        assert report.get(section), f"Section '{section}' is empty or missing"


async def test_confidence_is_valid_enum(client):
    events = await _analyze(client, "rs1051730")
    complete = next(e for e in events if e["type"] == "complete")
    confidence = complete["data"]["report"]["confidence"]
    assert confidence in VALID_CONFIDENCE, f"confidence={confidence!r} not in {VALID_CONFIDENCE}"


# ── Multiple variant IDs (checklist items 8-9) ───────────────────────────────


@pytest.mark.parametrize(
    "rs_id",
    [
        "rs1051730",  # CHRNA3 — nicotine dependence
        "rs429358",  # APOE ε4 — Alzheimer's risk
        "rs1800562",  # HFE — hereditary haemochromatosis
    ],
)
async def test_analysis_succeeds_for_known_variants(client, rs_id):
    async def _stream_for_id(rid: str):
        async for chunk in _fake_stream(rid):
            yield chunk

    events = await _analyze(client, rs_id, stream=_stream_for_id)
    complete = next((e for e in events if e["type"] == "complete"), None)
    assert complete is not None, f"No complete event for {rs_id}"
    assert complete["data"]["report"]["variant_id"] == rs_id


# ── Error handling ────────────────────────────────────────────────────────────


async def test_agent_error_emits_error_event(client):
    async def _error_stream(rs_id: str):
        yield f"event: error\ndata: {json.dumps({'error': 'Agent unavailable'})}\n\n"

    events = await _analyze(client, "rs1051730", stream=_error_stream)
    error_events = [e for e in events if e["type"] == "error"]
    assert error_events, "Expected an 'error' SSE event"
    assert "error" in error_events[0]["data"]


async def test_no_report_extracted_emits_complete_with_null_report(client):
    async def _no_report_stream(rs_id: str):
        yield f"event: complete\ndata: {json.dumps({'report': None, 'error': 'Could not extract structured report'})}\n\n"  # noqa: E501

    events = await _analyze(client, "rs1051730", stream=_no_report_stream)
    complete = next(e for e in events if e["type"] == "complete")
    assert complete["data"]["report"] is None
    assert "error" in complete["data"]


# ── Source badges (checklist item 7) — URL shape ─────────────────────────────


async def test_clinvar_source_url_format(client):
    events = await _analyze(client, "rs1051730")
    complete = next(e for e in events if e["type"] == "complete")
    sources = complete["data"]["report"].get("sources", [])
    clinvar = next((s for s in sources if s.get("db") == "ClinVar"), None)
    if clinvar and clinvar.get("url"):
        assert "ncbi.nlm.nih.gov/clinvar" in clinvar["url"], (
            f"Unexpected ClinVar URL: {clinvar['url']}"
        )
