import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from ..agent.managed_agent import ensure_agent_exists, run_analysis_streaming
from ..models.schemas import VariantRequest

load_dotenv()

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="VariantAI API",
    version="0.9.0",
    description="Genomic variant analysis powered by Google Managed Agents (Gemini 3.5 Flash)",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
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
    return {"status": "ok", "version": "0.9.0"}


@app.get("/api/suggest")
async def suggest_variants(q: str = ""):
    """Return up to 5 rsID suggestions matching the typed prefix via NCBI dbSNP."""
    q = q.strip().lower()
    if not q.startswith("rs"):
        return {"suggestions": []}

    numeric = q[2:]
    if len(numeric) < 2 or not numeric.isdigit():
        return {"suggestions": []}

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                params={
                    "db": "snp",
                    "term": f"{numeric}*[rs]",
                    "retmode": "json",
                    "retmax": 5,
                    "api_key": os.environ.get("NCBI_API_KEY", ""),
                },
            )
        ids = resp.json().get("esearchresult", {}).get("idlist", [])
        suggestions = [f"rs{id_}" for id_ in ids if f"rs{id_}" != q]
        return {"suggestions": suggestions[:5]}
    except Exception:
        return {"suggestions": []}


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
