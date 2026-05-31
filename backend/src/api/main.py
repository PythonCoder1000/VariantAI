import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from ..agent import memory
from ..agent.chat import run_chat_streaming
from ..agent.managed_agent import ensure_agent_exists, run_analysis_streaming
from ..models.schemas import ChatRequest, VariantRequest

load_dotenv()

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="VariantAI API",
    version="0.10.1",
    description="Genomic variant analysis powered by Google Managed Agents (Gemini 3.5 Flash)",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Pre-create the Managed Agent on server startup so the first request isn't slow."""
    try:
        ensure_agent_exists()
    except Exception as e:
        print(f"Warning: Could not pre-create agent on startup: {e}")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "0.10.1"}


@app.post("/api/analyze")
@limiter.limit("5/minute")
async def analyze_variant(request: Request, body: VariantRequest):
    """
    Analyze a genomic rsID.

    Returns a Server-Sent Events stream. Clients should listen for:
      - event: progress   → agent is running, data.text = partial output
      - event: complete   → data.report = structured VariantReport JSON
      - event: not_found  → data.variant_id = rsID that was not found in any database
      - event: error      → data.error = error message
    """

    async def generate():
        async for chunk in run_analysis_streaming(body.variant_id):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/api/chat")
@limiter.limit("20/minute")
async def chat(request: Request, body: ChatRequest):
    """
    Ask a follow-up question about an analyzed variant.

    Returns a Server-Sent Events stream:
      - event: delta  → data.text = incremental answer tokens
      - event: done   → data.text = full answer, data.memories_added = saved facts
      - event: error  → data.error = error message
    """
    messages = [m.model_dump() for m in body.messages]

    async def generate():
        async for chunk in run_chat_streaming(body.variant_id, body.report, messages):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/memory")
async def get_memory():
    """Return all globally remembered facts the assistant has saved."""
    return {"items": memory.load_memory()}


@app.delete("/api/memory")
async def delete_memory():
    """Erase all saved global memory."""
    memory.clear_memory()
    return {"status": "cleared"}
