QUERY_GENE_SKILL = r"""
---
name: query-gene
description: Query NCBI Gene for gene function, description, chromosomal location, and summary
---
# NCBI Gene Query Skill

Reads gene symbol from /workspace/raw/dbsnp.json (genes[0].symbol).
Falls back to "UNKNOWN" if not found.

## Python Code

```python
import requests, json, os

def query_gene(gene_symbol: str) -> dict:
    if gene_symbol == "UNKNOWN" or not gene_symbol:
        return {"gene_symbol": gene_symbol, "found": False, "message": "No gene symbol available"}

    api_key = os.environ.get("NCBI_API_KEY", "")
    email = os.environ.get("NCBI_EMAIL", "")
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    search_resp = requests.get(
        f"{base}/esearch.fcgi",
        params={
            "db": "gene",
            "term": f"{gene_symbol}[gene]+AND+9606[taxid]+AND+alive[prop]",
            "retmode": "json",
            "retmax": 3,
            "api_key": api_key,
            "email": email,
        },
        timeout=15,
    )
    ids = search_resp.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return {"gene_symbol": gene_symbol, "found": False}

    summary_resp = requests.get(
        f"{base}/esummary.fcgi",
        params={"db": "gene", "id": ids[0], "retmode": "json", "api_key": api_key},
        timeout=15,
    )
    doc = summary_resp.json().get("result", {}).get(ids[0], {})

    return {
        "gene_symbol": gene_symbol,
        "found": True,
        "gene_id": ids[0],
        "name": doc.get("name", ""),
        "description": doc.get("description", ""),
        "summary": doc.get("summary", ""),
        "chromosome": doc.get("chromosome", ""),
        "location": doc.get("maplocation", ""),
    }

# Read gene symbol from dbSNP results
gene_symbol = "UNKNOWN"
try:
    with open("/workspace/raw/dbsnp.json") as f:
        dbsnp = json.load(f)
    genes = dbsnp.get("genes", [])
    if genes:
        gene_symbol = genes[0].get("symbol", "UNKNOWN")
except Exception:
    pass

result = query_gene(gene_symbol)
os.makedirs("/workspace/raw", exist_ok=True)
with open("/workspace/raw/gene.json", "w") as f:
    json.dump(result, f, indent=2)
print(json.dumps(result, indent=2))
```
"""
