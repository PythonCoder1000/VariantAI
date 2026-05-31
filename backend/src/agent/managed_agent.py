import asyncio
import json
import os
import re

from .agents_md import AGENTS_MD
from .client import get_client
from .skills import ALL_SKILLS

AGENT_ID = "variantai-agent"
BASE_AGENT = "antigravity-preview-05-2026"

# Domains the agent sandbox is allowed to reach
NETWORK_ALLOWLIST = [
    {"domain": "eutils.ncbi.nlm.nih.gov"},
    {"domain": "api.ncbi.nlm.nih.gov"},
    {"domain": "gnomad.broadinstitute.org"},
    {"domain": "rest.uniprot.org"},
    {"domain": "rest.ensembl.org"},
]

SYSTEM_INSTRUCTION = (
    "You are VariantAI. Your sole purpose is to analyze genomic rsIDs. "
    "Follow the workflow in AGENTS.md exactly: query all 7 databases in order, "
    "then generate a structured JSON report using the generate-report skill. "
    "Be factual. Only report information sourced directly from database results."
)


def _build_sources() -> list[dict]:
    """Build inline source list: AGENTS.md + all SKILL.md files."""
    sources = [{"type": "inline", "target": ".agents/AGENTS.md", "content": AGENTS_MD}]
    for skill_name, skill_content in ALL_SKILLS:
        sources.append(
            {
                "type": "inline",
                "target": f".agents/skills/{skill_name}/SKILL.md",
                "content": skill_content,
            }
        )
    return sources


def ensure_agent_exists() -> None:
    """Create the Managed Agent if it does not already exist in the project."""
    client = get_client()
    try:
        client.agents.get(id=AGENT_ID)
    except Exception:
        client.agents.create(
            id=AGENT_ID,
            base_agent=BASE_AGENT,
            system_instruction=SYSTEM_INSTRUCTION,
            base_environment={
                "type": "remote",
                "sources": _build_sources(),
                "network": {"allowlist": NETWORK_ALLOWLIST},
            },
        )


def _build_prompt(rs_id: str) -> str:
    """Build the analysis prompt, injecting NCBI credentials as env var instructions."""
    ncbi_api_key = os.environ.get("NCBI_API_KEY", "")
    ncbi_email = os.environ.get("NCBI_EMAIL", "")
    return f"""
Analyze genomic variant: {rs_id}

Set these environment variables before running any code:
```python
import os
os.environ["NCBI_API_KEY"] = "{ncbi_api_key}"
os.environ["NCBI_EMAIL"] = "{ncbi_email}"
```

Now follow your AGENTS.md workflow exactly, using {rs_id} wherever you see RS_ID_PLACEHOLDER:
1. Run the query-clinvar skill for {rs_id}
2. Run the query-dbsnp skill for {rs_id}
3. Run the query-gnomad skill for {rs_id}
4. Extract gene symbol from /workspace/raw/dbsnp.json
5. Run the query-gene skill using that gene symbol
6. Run the query-uniprot skill using that gene symbol
7. Run the query-pubmed skill for {rs_id} and the gene symbol
8. Run the query-ensembl skill for {rs_id}
9. Run the generate-report skill to produce the final JSON

Do not skip any step. Output the final report wrapped in ===REPORT_START=== / ===REPORT_END===.
""".strip()


def _extract_report(output: str) -> dict | None:
    """Parse the structured JSON report from agent output.

    Tries in order:
    1. Exact ===REPORT_START=== / ===REPORT_END=== markers (with optional spaces).
    2. Same markers but the JSON is wrapped in a markdown code fence inside them.
    3. Fallback: character-level scan for any top-level JSON object that contains
       all five required report sections.
    """
    REQUIRED = {
        "clinical_risk",
        "gene_function",
        "structural_impact",
        "research_summary",
        "bottom_line",
    }

    # Strategy 1 & 2: sentinel markers, tolerant of spaces and code fences
    marker_match = re.search(
        r"={3}\s*REPORT_START\s*={3}\s*(.*?)\s*={3}\s*REPORT_END\s*={3}",
        output,
        re.DOTALL | re.IGNORECASE,
    )
    if marker_match:
        content = marker_match.group(1).strip()
        # Strip surrounding markdown code fences (```json ... ``` or ``` ... ```)
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content).strip()
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    # Strategy 3: scan for any top-level JSON object with all 5 required fields
    depth = 0
    start = None
    for i, ch in enumerate(output):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    data = json.loads(output[start : i + 1])
                    if isinstance(data, dict) and REQUIRED.issubset(data.keys()):
                        return data
                except json.JSONDecodeError:
                    pass
                start = None

    return None


def _delta_text(delta) -> str:
    """Extract streamable text from a ``step.delta`` event's ``delta`` object.

    The agent's prose and the final report stream as ``text`` deltas; skill
    execution surfaces as ``arguments_delta`` / ``code_execution_call`` (the
    code) and ``code_execution_result`` (stdout). All carry the keywords the
    frontend uses for progress, and the report JSON arrives in ``text``.
    """
    if delta is None:
        return ""
    dtype = getattr(delta, "type", None)
    if dtype == "text":
        return getattr(delta, "text", "") or ""
    if dtype == "arguments_delta":
        return getattr(delta, "arguments", "") or ""
    if dtype == "code_execution_call":
        args = getattr(delta, "arguments", None)
        return (getattr(args, "code", "") or "") if args is not None else ""
    if dtype == "code_execution_result":
        return getattr(delta, "result", "") or ""
    return ""


def _step_text(step) -> str:
    """Extract text from a full ``Step`` object (carried by ``step.start``)."""
    if step is None:
        return ""
    stype = getattr(step, "type", None)
    if stype == "model_output":
        return "".join(
            content.text
            for content in (getattr(step, "content", None) or [])
            if getattr(content, "type", None) == "text" and getattr(content, "text", None)
        )
    if stype == "code_execution_call":
        args = getattr(step, "arguments", None)
        return (getattr(args, "code", "") or "") if args is not None else ""
    if stype == "code_execution_result":
        return getattr(step, "result", "") or ""
    return ""


async def run_analysis_streaming(rs_id: str):
    """
    Async generator that yields SSE-formatted strings.

    Yields lines in one of these formats:
      "event: progress\\ndata: {\"text\": \"...\"}\\n\\n"
      "event: complete\\ndata: {\"report\": {...}}\\n\\n"
      "event: error\\ndata: {\"error\": \"...\"}\\n\\n"

    The Google genai SDK streaming call is synchronous, so it is run in a
    thread via asyncio.to_thread to avoid blocking the FastAPI event loop.
    """
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    def _run_sync() -> None:
        client = get_client()
        ensure_agent_exists()
        prompt = _build_prompt(rs_id)
        full_output = ""

        try:
            stream = client.interactions.create(
                agent=AGENT_ID,
                input=prompt,
                environment="remote",
                stream=True,
            )

            for event in stream:
                event_type = getattr(event, "event_type", None)

                # Surface agent-side failures immediately.
                if event_type == "error":
                    err = getattr(event, "error", None)
                    message = (
                        getattr(err, "message", None)
                        or getattr(err, "code", None)
                        or "Agent returned an error event"
                    )
                    raise RuntimeError(message)

                if event_type == "interaction.status_update":
                    status = getattr(event, "status", None)
                    if status in ("failed", "cancelled", "budget_exceeded"):
                        raise RuntimeError(f"Interaction {status}")
                    continue

                # Real output streams via step.delta (incremental) and
                # step.start (full step). The interaction.completed event
                # intentionally carries empty steps, so we never rely on it.
                if event_type == "step.delta":
                    text = _delta_text(getattr(event, "delta", None))
                elif event_type == "step.start":
                    text = _step_text(getattr(event, "step", None))
                else:
                    text = ""

                if text:
                    full_output += text
                    sse = f"event: progress\ndata: {json.dumps({'text': text})}\n\n"
                    loop.call_soon_threadsafe(queue.put_nowait, sse)

            report = _extract_report(full_output)
            if report:
                sse = f"event: complete\ndata: {json.dumps({'report': report})}\n\n"
            else:
                payload = json.dumps(
                    {
                        "report": None,
                        "raw_output": full_output,
                        "error": "Could not extract structured report",
                    }
                )
                sse = f"event: complete\ndata: {payload}\n\n"
            loop.call_soon_threadsafe(queue.put_nowait, sse)

        except Exception as exc:
            sse = f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
            loop.call_soon_threadsafe(queue.put_nowait, sse)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

    asyncio.create_task(asyncio.to_thread(_run_sync))

    while True:
        item = await queue.get()
        if item is None:
            break
        yield item
