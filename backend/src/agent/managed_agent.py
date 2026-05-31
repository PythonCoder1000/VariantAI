import asyncio
import json
import os
import re

from ..models.schemas import VariantReport
from .agents_md import AGENTS_MD
from .client import get_client
from .skills import ALL_SKILLS

# ---------------------------------------------------------------------------
# Function-calling tool: submit_report
# The agent calls this instead of printing JSON markers, giving us guaranteed
# structured output without any text parsing.
#
# The Managed Agents API expects a flat ToolParam dict — {type, name,
# description, parameters} where `parameters` is a plain JSON Schema object —
# NOT the google.genai.types.Tool(function_declarations=...) wrapper used by
# the base Gemini models API.
# ---------------------------------------------------------------------------
SUBMIT_REPORT_TOOL: dict = {
    "type": "function",
    "name": "submit_report",
    "description": (
        "Submit the final structured genomic variant analysis report. "
        "Call this ONCE after completing all 8 database queries."
    ),
    "parameters": {
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
    },
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
9. Read all /workspace/raw/*.json files, synthesize the results, and call the submit_report function

Do not skip any step. For step 9, call submit_report() — do not print markers.
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


def _fc_args_from_step(step) -> dict | None:
    """Return submit_report arguments from a single Step, if it is that call.

    A ``FunctionCallStep`` has ``type == "function_call"``, ``name``, and
    ``arguments`` — which the Managed Agents SDK delivers as an already-parsed
    ``dict`` (not a JSON string). We ignore empty-argument steps so a partially
    populated ``step.start`` never clobbers the final value.
    """
    if step is None:
        return None
    if getattr(step, "type", None) != "function_call":
        return None
    if getattr(step, "name", None) != "submit_report":
        return None
    args = getattr(step, "arguments", None)
    if isinstance(args, dict) and args:
        return args
    if isinstance(args, str) and args.strip():
        try:
            parsed = json.loads(args)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _fc_args_from_steps(steps) -> dict | None:
    """Scan a list of Steps (from interaction.completed) for the submit_report call."""
    for step in steps or []:
        args = _fc_args_from_step(step)
        if args is not None:
            return args
    return None


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
                tools=[SUBMIT_REPORT_TOOL],
            )

            fc_report: dict | None = None

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
                # full list of steps, including the submit_report FunctionCallStep
                # with its fully-populated arguments dict.
                if event_type == "interaction.completed":
                    interaction = getattr(event, "interaction", None)
                    steps = getattr(interaction, "steps", None) if interaction else None
                    fc = _fc_args_from_steps(steps)
                    if fc is not None:
                        fc_report = fc
                    continue

                # Real output streams via step.delta (incremental) and step.start
                # (full step). A function call may also appear as a complete
                # step.start — capture it as a fallback to interaction.completed.
                if event_type == "step.start":
                    step = getattr(event, "step", None)
                    fc = _fc_args_from_step(step)
                    if fc is not None:
                        fc_report = fc
                    text = _step_text(step)
                elif event_type == "step.delta":
                    text = _delta_text(getattr(event, "delta", None))
                else:
                    text = ""

                if text:
                    full_output += text
                    sse = f"event: progress\ndata: {json.dumps({'text': text})}\n\n"
                    loop.call_soon_threadsafe(queue.put_nowait, sse)

            # Prefer the structured function call; fall back to text-marker parsing
            # in case the model printed a report instead of calling submit_report.
            report = fc_report or _extract_report(full_output)
            print(
                f"[VariantAI] rs_id={rs_id} fc_call={fc_report is not None} "
                f"report_parsed={report is not None} output_len={len(full_output)}",
                flush=True,
            )
            if report:
                report = _normalize_report(report, rs_id)
                sse = f"event: complete\ndata: {json.dumps({'report': report})}\n\n"
            else:
                payload = json.dumps(
                    {
                        "report": None,
                        "raw_output": full_output[:2000],
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
