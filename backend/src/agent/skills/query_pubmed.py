QUERY_PUBMED_SKILL = r"""
---
name: query-pubmed
description: Query PubMed for the 5 most relevant research papers about this variant and gene
---
# PubMed Query Skill

Searches by rsID. If a gene symbol is available (from dbSNP), broadens the search.
Replace RS_ID_PLACEHOLDER with the actual rsID.

## Python Code

```python
import requests, json, os

def query_pubmed(rs_id: str, gene_symbol: str = "") -> dict:
    api_key = os.environ.get("NCBI_API_KEY", "")
    email = os.environ.get("NCBI_EMAIL", "")
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    term = rs_id
    if gene_symbol and gene_symbol not in ("UNKNOWN", ""):
        term = f"{rs_id} OR ({gene_symbol}[gene] AND (variant OR mutation OR polymorphism))"

    search_resp = requests.get(
        f"{base}/esearch.fcgi",
        params={
            "db": "pubmed",
            "term": term,
            "retmode": "json",
            "retmax": 5,
            "sort": "relevance",
            "api_key": api_key,
            "email": email,
        },
        timeout=15,
    )
    pmids = search_resp.json().get("esearchresult", {}).get("idlist", [])
    if not pmids:
        return {"rs_id": rs_id, "found": False, "papers": []}

    summary_resp = requests.get(
        f"{base}/esummary.fcgi",
        params={"db": "pubmed", "id": ",".join(pmids), "retmode": "json", "api_key": api_key},
        timeout=15,
    )
    summary_data = summary_resp.json()

    papers = []
    for pmid in pmids:
        doc = summary_data.get("result", {}).get(pmid, {})
        doi = next(
            (i.get("value") for i in doc.get("articleids", []) if i.get("idtype") == "doi"),
            None,
        )
        papers.append({
            "pmid": pmid,
            "title": doc.get("title", ""),
            "authors": [a.get("name", "") for a in doc.get("authors", [])[:3]],
            "journal": doc.get("source", ""),
            "pub_date": doc.get("pubdate", ""),
            "doi": doi,
        })

    return {"rs_id": rs_id, "found": True, "papers": papers}

gene_symbol = "UNKNOWN"
try:
    with open("/workspace/raw/dbsnp.json") as f:
        dbsnp = json.load(f)
    genes = dbsnp.get("genes", [])
    if genes:
        gene_symbol = genes[0].get("symbol", "UNKNOWN")
except Exception:
    pass

result = query_pubmed("RS_ID_PLACEHOLDER", gene_symbol)
os.makedirs("/workspace/raw", exist_ok=True)
with open("/workspace/raw/pubmed.json", "w") as f:
    json.dump(result, f, indent=2)
print(json.dumps(result, indent=2))
```
"""
