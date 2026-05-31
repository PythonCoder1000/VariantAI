import re

from pydantic import BaseModel, field_validator


class VariantRequest(BaseModel):
    variant_id: str

    @field_validator("variant_id")
    @classmethod
    def validate_rs_id(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^rs\d+$", v, re.IGNORECASE):
            raise ValueError(
                "Only rsID format is supported (e.g. rs1051730). "
                "Must start with 'rs' followed by digits only."
            )
        return v.lower()


class VariantReport(BaseModel):
    variant_id: str
    gene: str | None = None
    variant_type: str | None = None
    clinical_risk: str
    gene_function: str
    structural_impact: str
    research_summary: str
    bottom_line: str
    confidence: str = "medium"  # "high" | "medium" | "low"
    sources: list[dict] = []


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    variant_id: str
    report: dict | None = None
    messages: list[ChatMessage]

    @field_validator("messages")
    @classmethod
    def non_empty(cls, v: list[ChatMessage]) -> list[ChatMessage]:
        if not v:
            raise ValueError("messages must contain at least one message")
        if v[-1].role != "user":
            raise ValueError("the last message must be from the user")
        return v
