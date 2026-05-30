QUERY_UNIPROT_SKILL = r"""
---
name: query-uniprot
description: Query UniProt Swiss-Prot for protein function, domains, and disease associations for the gene symbol
---
# UniProt Query Skill

Reads gene symbol from /workspace/raw/dbsnp.json. Queries only reviewed (Swiss-Prot) entries.

## Python Code

```python
import requests, json, os

def query_uniprot(gene_symbol: str) -> dict:
    if gene_symbol == "UNKNOWN" or not gene_symbol:
        return {"gene_symbol": gene_symbol, "found": False}

    resp = requests.get(
        "https://rest.uniprot.org/uniprotkb/search",
        params={
            "query": f"gene_exact:{gene_symbol} AND organism_id:9606 AND reviewed:true",
            "fields": "accession,protein_name,gene_names,cc_function,cc_domain,cc_disease,sequence",
            "format": "json",
            "size": 3,
        },
        timeout=15,
    )
    if resp.status_code != 200:
        return {"gene_symbol": gene_symbol, "found": False, "error": f"HTTP {resp.status_code}"}

    results = resp.json().get("results", [])
    if not results:
        return {"gene_symbol": gene_symbol, "found": False, "message": "No Swiss-Prot entry found"}

    entry = results[0]

    def extract_comments(comments, comment_type):
        return [
            text.get("value", "")
            for c in comments
            if c.get("commentType") == comment_type
            for text in c.get("texts", [])
        ]

    comments = entry.get("comments", [])
    diseases = [
        {"name": c.get("disease", {}).get("diseaseId", ""),
         "description": c.get("disease", {}).get("description", "")}
        for c in comments if c.get("commentType") == "DISEASE"
    ]

    return {
        "gene_symbol": gene_symbol,
        "found": True,
        "accession": entry.get("primaryAccession", ""),
        "protein_name": (
            entry.get("proteinDescription", {})
                 .get("recommendedName", {})
                 .get("fullName", {})
                 .get("value", "")
        ),
        "functions": extract_comments(comments, "FUNCTION")[:3],
        "domains": extract_comments(comments, "DOMAIN")[:3],
        "diseases": diseases[:5],
        "sequence_length": entry.get("sequence", {}).get("length", 0),
    }

gene_symbol = "UNKNOWN"
try:
    with open("/workspace/raw/dbsnp.json") as f:
        dbsnp = json.load(f)
    genes = dbsnp.get("genes", [])
    if genes:
        gene_symbol = genes[0].get("symbol", "UNKNOWN")
except Exception:
    pass

result = query_uniprot(gene_symbol)
os.makedirs("/workspace/raw", exist_ok=True)
with open("/workspace/raw/uniprot.json", "w") as f:
    json.dump(result, f, indent=2)
print(json.dumps(result, indent=2))
```
"""
