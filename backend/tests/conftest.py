import json
from typing import AsyncGenerator
from unittest.mock import patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.api.main import app

# ── A minimal but realistic SSE stream for tests that exercise the full endpoint ──

SAMPLE_REPORT = {
    "variant_id": "rs1051730",
    "gene": "CHRNA3",
    "variant_type": "SNP (missense)",
    "clinical_risk": "ClinVar classifies this as Risk factor for nicotine dependence.",
    "gene_function": "CHRNA3 encodes the alpha-3 subunit of the nicotinic acetylcholine receptor.",
    "structural_impact": "Missense variant p.Asn398Ser; SIFT tolerated (0.23), PolyPhen benign.",
    "research_summary": "Allele frequency ~32% in European ancestry (gnomAD). Smith et al. (2021).",
    "bottom_line": "A common variant in people of European descent with modest lung-cancer risk.",
    "confidence": "high",
    "sources": [{"db": "ClinVar", "url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/1234/"}],
}

PROGRESS_KEYWORDS = ["clinvar", "dbsnp", "gnomad", "gene", "uniprot", "pubmed", "ensembl"]


async def _fake_stream(rs_id: str) -> AsyncGenerator[str, None]:
    for kw in PROGRESS_KEYWORDS:
        yield f"event: progress\ndata: {json.dumps({'text': f'querying {kw}...'})}\n\n"
    report = {**SAMPLE_REPORT, "variant_id": rs_id}
    yield f"event: complete\ndata: {json.dumps({'report': report})}\n\n"


@pytest_asyncio.fixture
async def client():
    with patch("src.api.main.ensure_agent_exists"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


# ── SSE parsing helper used across multiple test modules ──


def parse_sse(text: str) -> list[dict]:
    """Parse an SSE body into a list of {type, data} dicts."""
    events: list[dict] = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event_type = None
        data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event_type = line[7:].strip()
            elif line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError:
                    data = line[6:]
        if event_type is not None and data is not None:
            events.append({"type": event_type, "data": data})
    return events
