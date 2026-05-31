GENERATE_REPORT_SKILL = r"""
---
name: generate-report
description: Read all /workspace/raw/*.json results and synthesize a structured plain-language clinical report
---
# Generate Report Skill

Load all raw database results, then synthesize into structured JSON.

## Required Output Schema

```json
{
  "variant_id": "rs1051730",
  "gene": "CHRNA3",
  "variant_type": "SNP (missense)",
  "clinical_risk": "1-3 sentences. ClinVar classification, specific disease associations, review status.",
  "gene_function": "1-3 sentences. What this gene/protein does biologically. Use Gene summary + UniProt function.",
  "structural_impact": "1-3 sentences. Amino acid change, affected domain, SIFT/PolyPhen predictions + interpretation.",
  "research_summary": "2-4 sentences. Population frequency from gnomAD (e.g. '32% in European ancestry'). Number of ClinVar submissions. Key paper citations (First Author Year).",
  "bottom_line": "2-3 sentences in plain language for a non-specialist. Avoid jargon. State whether this is dangerous, common, or uncertain. Suggest actionable context (e.g. 'consult a genetic counselor').",
  "confidence": "high",
  "sources": [
    {"db": "ClinVar", "url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/<accession>/"},
    {"db": "gnomAD", "allele_frequency": 0.322},
    {"db": "PubMed", "pmids": ["21943158", "28604731"]}
  ]
}
```

## Confidence Level Rules

- **"high"**: ClinVar found with expert-panel or multiple-submitter review + gnomAD data present + ≥3 papers
- **"medium"**: ClinVar found but limited review OR gnomAD data missing OR <3 papers
- **"low"**: Not in ClinVar, or most database queries returned errors

## Section Writing Guidelines

**clinical_risk**: Lead with ClinVar's exact classification string (e.g. "Pathogenic", "Likely benign",
"Risk factor"). Name the specific diseases from the conditions list. Note review status —
"expert panel reviewed" is the most authoritative. Example: "ClinVar classifies this variant as
Pathogenic with expert panel review, associated with Hereditary breast and ovarian cancer syndrome
(BRCA1-related)."

**gene_function**: Draw from NCBI Gene summary and UniProt function fields. Translate scientific
language: replace "encodes" with "produces", avoid Latin gene names without explanation.
Example: "BRCA1 produces a tumor suppressor protein that helps repair damaged DNA and maintain
genomic stability. It plays a central role in the BRCA1-BARD1 complex involved in DNA double-strand
break repair."

**structural_impact**: Use Ensembl VEP data. State the consequence type first (missense, stop-gained,
frameshift, synonymous, etc.). Include amino acid change if available (format: p.Asn398Ser). Interpret
SIFT and PolyPhen scores: SIFT <0.05 = "predicted damaging"; PolyPhen >0.9 = "probably damaging";
0.5–0.9 = "possibly damaging"; <0.5 = "benign". Example: "This is a missense variant (p.Asn398Ser)
in the DNA-binding domain. SIFT predicts it is tolerated (score 0.23); PolyPhen predicts possibly
damaging (score 0.712)."

**research_summary**: Lead with gnomAD allele frequency. Format as a percentage if >1%, or scientific
notation if rare (e.g. "6.3 × 10⁻⁵"). Mention which population it's most common in from the
populations array. Then cite ClinVar submission count. Then reference key PubMed papers by
"First Author et al. (Year)". Example: "This variant has an allele frequency of 32.2% in European
ancestry individuals in gnomAD (ac=41,234, an=128,010). Over 40 studies have investigated it.
Smith et al. (2021) demonstrated its association with nicotine dependence susceptibility."

**bottom_line**: Avoid all jargon. Write as if explaining to a patient. Address three questions:
(1) Is this dangerous? (2) How common is it? (3) What should they do with this information?
Example: "This is a common genetic variant found in roughly 1 in 3 people of European descent.
While it modestly increases the risk of lung cancer in people who smoke, it does not cause disease
on its own. If you are concerned about your personal risk, speaking with a genetic counselor
is recommended."

## How to Complete Step 9

Do NOT run Python code for this step. Instead:

1. Read all raw files from /workspace/raw/ (clinvar, dbsnp, gnomad, gene, uniprot, pubmed, ensembl)
2. Synthesize the data according to the section guidelines above
3. Output your final message as ONLY the JSON report object conforming to the schema above

Your final message must contain nothing but the JSON object — no prose, no code fences,
no markers. It must include every required field shown in the schema.
"""
