"""Unit tests for _extract_report — the JSON extraction logic in managed_agent.py."""

import json

import pytest

from src.agent.managed_agent import _extract_report

FULL_REPORT = {
    "variant_id": "rs1051730",
    "gene": "CHRNA3",
    "clinical_risk": "Risk factor for nicotine dependence.",
    "gene_function": "Encodes nicotinic acetylcholine receptor alpha-3 subunit.",
    "structural_impact": "Missense variant p.Asn398Ser.",
    "research_summary": "Allele frequency ~32% in European populations.",
    "bottom_line": "Common variant; consult a genetic counselor.",
    "confidence": "high",
    "sources": [],
}


def _json(report=None) -> str:
    return json.dumps(report or FULL_REPORT)


# ── Sentinel markers (Strategy 1) ────────────────────────────────────────────


def test_extracts_with_exact_markers():
    text = f"===REPORT_START===\n{_json()}\n===REPORT_END==="
    assert _extract_report(text) == FULL_REPORT


def test_extracts_with_spaces_around_markers():
    text = f"=== REPORT_START ===\n{_json()}\n=== REPORT_END ==="
    assert _extract_report(text) == FULL_REPORT


def test_extracts_case_insensitive_markers():
    text = f"===report_start===\n{_json()}\n===report_end==="
    assert _extract_report(text) == FULL_REPORT


def test_extracts_markers_with_prose_before_and_after():
    text = f"Running analysis...\n===REPORT_START===\n{_json()}\n===REPORT_END===\nDone."
    assert _extract_report(text) == FULL_REPORT


# ── Markers with code fence (Strategy 2) ─────────────────────────────────────


def test_extracts_json_in_code_fence_inside_markers():
    text = f"===REPORT_START===\n```json\n{_json()}\n```\n===REPORT_END==="
    assert _extract_report(text) == FULL_REPORT


def test_extracts_json_in_plain_fence_inside_markers():
    text = f"===REPORT_START===\n```\n{_json()}\n```\n===REPORT_END==="
    assert _extract_report(text) == FULL_REPORT


# ── Standalone markdown code block (Strategy 3) ──────────────────────────────


def test_extracts_standalone_json_code_block():
    text = f"Here is the report:\n```json\n{_json()}\n```\nEnd."
    assert _extract_report(text) == FULL_REPORT


# ── Forward character scan (Strategy 4) ──────────────────────────────────────


def test_forward_scan_finds_json_object_without_markers():
    text = f"Agent output: {_json()} End."
    assert _extract_report(text) == FULL_REPORT


def test_forward_scan_skips_incomplete_objects():
    incomplete = '{"variant_id": "rs1", "gene": "X"}'  # missing all 5 required fields
    text = f"{incomplete} then {_json()}"
    result = _extract_report(text)
    assert result == FULL_REPORT


def test_forward_scan_survives_stray_closing_brace():
    # Simulates a Python f-string in streamed code: f"{base}/endpoint"
    # produces a stray `}` that used to break the depth counter permanently.
    fstring_code = 'url = f"{base}/endpoint"\n'
    text = fstring_code + _json()
    assert _extract_report(text) == FULL_REPORT


def test_forward_scan_survives_multiple_stray_braces():
    code_block = (
        'params = {"db": "clinvar", "term": f"{rs_id}[rs]"}\n'
        'headers = {"Accept": "application/json"}\n'
    )
    text = code_block + _json()
    assert _extract_report(text) == FULL_REPORT


def test_forward_scan_skips_deeply_nested_json():
    # An outer object that doesn't have the required keys wraps a valid report.
    outer = {"wrapper": FULL_REPORT}
    text = json.dumps(outer)
    # The outer dict does NOT have the required keys, so None is expected.
    assert _extract_report(text) is None


# ── Reverse scan (Strategy 5) ─────────────────────────────────────────────────


def test_reverse_scan_finds_report_at_end():
    # Simulates 198KB of code execution output followed by the final report.
    noise = '{"rs_id": "rs1051730", "found": true}\n' * 100  # database query results
    code = 'url = f"{base}/api"\nparams = {"key": "val"}\n' * 50
    text = noise + code + _json()
    assert _extract_report(text) == FULL_REPORT


# ── Invalid / no JSON ─────────────────────────────────────────────────────────


def test_returns_none_when_no_json():
    assert _extract_report("No JSON here.") is None


def test_returns_none_when_json_missing_required_fields():
    partial = json.dumps({"variant_id": "rs1", "gene": "X"})
    assert _extract_report(partial) is None


def test_returns_none_on_empty_string():
    assert _extract_report("") is None


def test_returns_none_on_malformed_json_in_markers():
    text = "===REPORT_START===\n{broken json\n===REPORT_END==="
    assert _extract_report(text) is None


# ── Confidence enum passthrough ───────────────────────────────────────────────


@pytest.mark.parametrize("confidence", ["high", "medium", "low"])
def test_confidence_values_are_preserved(confidence):
    report = {**FULL_REPORT, "confidence": confidence}
    text = f"===REPORT_START===\n{json.dumps(report)}\n===REPORT_END==="
    assert _extract_report(text)["confidence"] == confidence
