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
