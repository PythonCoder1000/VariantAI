import asyncio
import json
import os
import re

from ..models.schemas import VariantReport
from .agents_md import AGENTS_MD
from .client import get_client
from .skills import ALL_SKILLS

# ---------------------------------------------------------------------------
# Structured output via response_format.
#
# Custom `function` tools are NOT permitted when interacting with a stored
# code-execution agent ("Tool 'function' is not allowed when interacting with
# this agent") — the only agent-level tool types are code_execution,
# google_search, url_context and mcp_server. The Managed Agents API's native
# mechanism for guaranteed structured output is a `response_format` of type
# "text" with mime_type "application/json" and a JSON Schema, which constrains
# the agent's final message to valid JSON conforming to the schema.
# ---------------------------------------------------------------------------
REPORT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "variant_id": {"type": "string"},
        "gene": {"type": "string"},
        "variant_type": {"type": "string"},
        "clinical_risk": {"type": "string"},
        "gene_function": {"type": "string"},
        "structural_impact": {"type": "string"},
        "research_summary": {"type": "string"},
        "bottom_line": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "sources": {"type": "array", "items": {"type": "object"}},
    },
    "required": [
        "variant_id",
        "clinical_risk",
        "gene_function",
        "structural_impact",
        "research_summary",
        "bottom_line",
        "confidence",
        "sources",
    ],
}

REPORT_RESPONSE_FORMAT: dict = {
    "type": "text",
    "mime_type": "application/json",
    "schema": REPORT_SCHEMA,
}

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
9. Read all /workspace/raw/*.json files, synthesize the results, and output the final report

Do not skip any step. For step 9, your final message must be ONLY the JSON report object
(no prose, no code fences, no markers) conforming to the required schema.
""".strip()


def _extract_report(output: str) -> dict | None:
    """Parse the structured JSON report from agent output.

    Tries in order:
    1. ===REPORT_START=== / ===REPORT_END=== markers (tolerant of spaces/case).
    2. Same markers with a markdown code fence inside them.
    3. Standalone markdown ```json ... ``` code block.
    4. Forward character scan for top-level JSON objects with all required fields.
       Depth is reset on stray closing braces so that Python f-strings / code
       execution output (which contain unbalanced ``{`` / ``}``) don't break the
       tracker for the rest of the document.
    5. Reverse scan from the end of the output — the report is always the last
       thing the agent writes, so scanning backwards finds it fastest.
    """
    REQUIRED = {
        "clinical_risk",
        "gene_function",
        "structural_impact",
        "research_summary",
        "bottom_line",
    }

    def _try(candidate: str) -> dict | None:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict) and REQUIRED.issubset(data.keys()):
                return data
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    # Strategy 1 & 2: sentinel markers, tolerant of spaces and code fences
    marker_match = re.search(
        r"={3}\s*REPORT_START\s*={3}\s*(.*?)\s*={3}\s*REPORT_END\s*={3}",
        output,
        re.DOTALL | re.IGNORECASE,
    )
    if marker_match:
        content = marker_match.group(1).strip()
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content).strip()
        result = _try(content)
        if result is not None:
            return result

    # Strategy 3: standalone markdown JSON code block
    for block_match in re.finditer(r"```json\s*(.*?)\s*```", output, re.DOTALL):
        result = _try(block_match.group(1))
        if result is not None:
            return result

    # Strategy 4: forward character scan.
    # Reset depth on stray `}` so Python f-strings / code blocks don't cascade.
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
                result = _try(output[start : i + 1])
                if result is not None:
                    return result
                start = None
            elif depth < 0:
                # Stray closing brace (inside a Python string / code output).
                # Reset so the next `{` starts a fresh top-level object.
                depth = 0
                start = None

    # Strategy 5: reverse scan — walk backwards finding brace-balanced blocks.
    # The JSON report is the last thing the agent outputs, so this hits it first.
    depth = 0
    end = None
    for i in range(len(output) - 1, -1, -1):
        ch = output[i]
        if ch == "}":
            if depth == 0:
                end = i
            depth += 1
        elif ch == "{":
            depth -= 1
            if depth == 0 and end is not None:
                result = _try(output[i : end + 1])
                if result is not None:
                    return result
                end = None
            elif depth < 0:
                depth = 0
                end = None

    return None


def _final_text_from_steps(steps) -> str:
    """Concatenate the text of all model_output steps in a completed interaction.

    With response_format=json the agent's final model_output carries the report
    JSON. The completed interaction holds the full, non-streamed step list, so
    this is the authoritative source for extraction (more reliable than the
    accumulated stream deltas).
    """
    parts: list[str] = []
    for step in steps or []:
        if getattr(step, "type", None) == "model_output":
            for content in getattr(step, "content", None) or []:
                if getattr(content, "type", None) == "text" and getattr(content, "text", None):
                    parts.append(content.text)
    return "".join(parts)


def _normalize_report(report: dict, rs_id: str) -> dict:
    """Coerce a raw report dict through the VariantReport model.

    Guarantees the frontend receives every section plus the ``confidence`` and
    ``sources`` defaults. If validation fails (e.g. a required section is
    missing), fall back to the raw dict with ``variant_id`` backfilled so the
    response is never empty.
    """
    report.setdefault("variant_id", rs_id)
    try:
        return VariantReport(**report).model_dump()
    except Exception:
        return report


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
                response_format=[REPORT_RESPONSE_FORMAT],
            )

            final_text = ""

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
                    if status in ("failed", "cancelled", "incomplete", "budget_exceeded"):
                        raise RuntimeError(f"Interaction {status}")
                    continue

                # Authoritative source: the completed interaction carries the
                # full, non-streamed step list. With response_format=json the
                # report JSON is the concatenated model_output text.
                if event_type == "interaction.completed":
                    interaction = getattr(event, "interaction", None)
                    steps = getattr(interaction, "steps", None) if interaction else None
                    ft = _final_text_from_steps(steps)
                    if ft:
                        final_text = ft
                    print(
                        f"[VariantAI] interaction.completed:"
                        f" has_interaction={interaction is not None}"
                        f" has_steps={steps is not None}"
                        f" step_count={len(steps) if steps else 0}"
                        f" final_text_len={len(ft)}",
                        flush=True,
                    )
                    continue

                # Stream progress text to the frontend (step.delta incremental,
                # step.start full step).
                if event_type == "step.start":
                    text = _step_text(getattr(event, "step", None))
                elif event_type == "step.delta":
                    text = _delta_text(getattr(event, "delta", None))
                else:
                    text = ""

                if text:
                    full_output += text
                    sse = f"event: progress\ndata: {json.dumps({'text': text})}\n\n"
                    loop.call_soon_threadsafe(queue.put_nowait, sse)

            # Prefer the authoritative final text from the completed interaction;
            # fall back to the accumulated stream output.
            report = _extract_report(final_text) or _extract_report(full_output)
            print(
                f"[VariantAI] rs_id={rs_id} report_parsed={report is not None} "
                f"final_len={len(final_text)} stream_len={len(full_output)}",
                flush=True,
            )
            if report is None:
                # Log the tail of the stream so the failure can be diagnosed.
                tail = (final_text or full_output)[-3000:]
                print(f"[VariantAI] stream_tail:\n{tail}", flush=True)
            if report:
                report = _normalize_report(report, rs_id)
                sse = f"event: complete\ndata: {json.dumps({'report': report})}\n\n"
            else:
                payload = json.dumps(
                    {
                        "report": None,
                        "raw_output": (final_text or full_output)[:2000],
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
