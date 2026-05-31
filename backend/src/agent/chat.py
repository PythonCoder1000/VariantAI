"""Follow-up chat about an analyzed variant.

Uses a plain Gemini model (``gemini-2.5-flash``) rather than the code-execution
Managed Agent: follow-ups are conversational, grounded in the already-computed
report, so they don't need the 7-database sandbox workflow (and shouldn't pay for
it). The report JSON + global memory are injected as context.

The assistant can persist durable facts by ending a reply with one or more
``[[MEMORY: ...]]`` directives; these are parsed out (never shown to the user)
and written to the global memory store.
"""

import asyncio
import json
import re

from google.genai import types

from . import memory
from .client import get_client

CHAT_MODEL = "gemini-2.5-flash"

_MEMORY_RE = re.compile(r"\[\[MEMORY:\s*(.*?)\]\]", re.DOTALL | re.IGNORECASE)


def extract_memories(text: str) -> tuple[str, list[str]]:
    """Split ``[[MEMORY: ...]]`` directives out of ``text``.

    Returns ``(clean_text, memories)`` — the visible text with markers removed
    and the list of memory strings found.
    """
    memories = [m.strip() for m in _MEMORY_RE.findall(text) if m.strip()]
    clean = _MEMORY_RE.sub("", text).strip()
    return clean, memories


def _build_system_instruction(variant_id: str, report: dict | None) -> str:
    report_block = json.dumps(report, indent=2) if report else "(no structured report available)"
    return f"""You are VariantAI's assistant, helping a non-specialist understand the genomic
variant {variant_id}. A full analysis has already been produced; answer follow-up
questions about it clearly and conversationally.

## The report you are discussing
{report_block}

## What you remember about this user (global memory, persists across chats)
{memory.format_for_prompt()}

## How to answer
- Ground every clinical claim in the report above. If the report doesn't cover
  something, you may add general, well-established genetics background — but say
  plainly when you are going beyond the report, and never invent specific
  statistics, classifications, or study results.
- Write in plain language. Briefly define jargon the first time you use it.
- Be concise: a few short paragraphs at most unless asked for depth.
- This is educational information, not medical advice. For decisions about their
  own health, remind the user to consult a clinician or genetic counselor — but
  only when it's genuinely relevant, not as boilerplate on every reply.

## Saving memory
If the user shares something durable and worth remembering across future
conversations (e.g. "I'm a clinician", "explain things simply", "I carry this
variant", a name to use), save it. To save, append at the VERY END of your reply,
each on its own line:
[[MEMORY: the concise fact to remember]]
Save only durable, useful facts — never one-off questions or trivia. If there is
nothing worth saving, do not emit any [[MEMORY:]] line."""


def _to_contents(messages: list[dict]) -> list[types.Content]:
    """Convert ``[{role, content}]`` history into genai Content objects.

    Roles map: user -> "user", assistant -> "model".
    """
    contents: list[types.Content] = []
    for msg in messages:
        role = "model" if msg.get("role") == "assistant" else "user"
        text = msg.get("content", "") or ""
        if not text:
            continue
        contents.append(types.Content(role=role, parts=[types.Part(text=text)]))
    return contents


async def run_chat_streaming(variant_id: str, report: dict | None, messages: list[dict]):
    """Async generator yielding SSE strings for a follow-up chat turn.

    Events:
      event: delta  data: {"text": "..."}                       (incremental tokens)
      event: done   data: {"text": "...", "memories_added": []} (final cleaned answer)
      event: error  data: {"error": "..."}
    """
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    def _run_sync() -> None:
        full = ""
        emitting = True
        try:
            client = get_client()
            stream = client.models.generate_content_stream(
                model=CHAT_MODEL,
                contents=_to_contents(messages),
                config=types.GenerateContentConfig(
                    system_instruction=_build_system_instruction(variant_id, report),
                    max_output_tokens=4000,
                    temperature=0.4,
                ),
            )
            for chunk in stream:
                piece = getattr(chunk, "text", None) or ""
                if not piece:
                    continue
                full += piece
                # Once a memory directive may be starting, stop streaming visible
                # text and just accumulate — the cleaned answer goes out in `done`.
                if emitting and "[[" in full:
                    emitting = False
                if emitting:
                    sse = f"event: delta\ndata: {json.dumps({'text': piece})}\n\n"
                    loop.call_soon_threadsafe(queue.put_nowait, sse)

            clean, memories = extract_memories(full)
            added = memory.add_memories(memories) if memories else []
            payload = json.dumps({"text": clean, "memories_added": [a["text"] for a in added]})
            loop.call_soon_threadsafe(queue.put_nowait, f"event: done\ndata: {payload}\n\n")
        except Exception as exc:
            sse = f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
            loop.call_soon_threadsafe(queue.put_nowait, sse)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    asyncio.create_task(asyncio.to_thread(_run_sync))

    while True:
        item = await queue.get()
        if item is None:
            break
        yield item
