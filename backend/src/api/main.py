import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from ..agent.managed_agent import ensure_agent_exists, run_analysis_streaming
from ..models.schemas import VariantRequest

load_dotenv()

app = FastAPI(
    title="VariantAI API",
    version="0.7.2",
    description="Genomic variant analysis powered by Google Managed Agents (Gemini 3.5 Flash)",
)

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
    return {"status": "ok", "version": "0.7.2"}


@app.post("/api/analyze")
async def analyze_variant(request: VariantRequest):
    """
    Analyze a genomic rsID.

    Returns a Server-Sent Events stream. Clients should listen for:
      - event: progress  → agent is running, data.text = partial output
      - event: complete  → data.report = structured VariantReport JSON
      - event: error     → data.error = error message
    """

    async def generate():
        async for chunk in run_analysis_streaming(request.variant_id):
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
