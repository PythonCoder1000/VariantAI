QUERY_CLINVAR_SKILL = r"""
---
name: query-clinvar
description: Query NCBI ClinVar for clinical significance, disease associations, and review status of a variant by rsID
---
# ClinVar Query Skill

Query ClinVar using NCBI E-utilities. Replace RS_ID_PLACEHOLDER with the actual rsID.

## Python Code

```python
import requests, json, os

def query_clinvar(rs_id: str) -> dict:
    api_key = os.environ.get("NCBI_API_KEY", "")
    email = os.environ.get("NCBI_EMAIL", "")
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    search_resp = requests.get(
        f"{base}/esearch.fcgi",
        params={
            "db": "clinvar",
            "term": f"{rs_id}[rs]",
            "retmode": "json",
            "retmax": 10,
            "api_key": api_key,
            "email": email,
        },
        timeout=15,
    )
    search_data = search_resp.json()
    ids = search_data.get("esearchresult", {}).get("idlist", [])

    if not ids:
        return {"rs_id": rs_id, "found": False, "clinical_significance": "Not found in ClinVar"}

    summary_resp = requests.get(
        f"{base}/esummary.fcgi",
        params={
            "db": "clinvar",
            "id": ",".join(ids[:5]),
            "retmode": "json",
            "api_key": api_key,
        },
        timeout=15,
    )
    summary_data = summary_resp.json()

    variants = []
    for var_id, doc in summary_data.get("result", {}).items():
        if var_id == "uids":
            continue
        variants.append({
            "accession": doc.get("accession", ""),
            "title": doc.get("title", ""),
            "clinical_significance": doc.get("clinical_significance", {}).get("description", "Unknown"),
            "review_status": doc.get("clinical_significance", {}).get("review_status", ""),
            "conditions": [t.get("name", "") for t in doc.get("trait_set", [])],
            "variation_type": doc.get("obj_type", ""),
        })

    return {"rs_id": rs_id, "found": True, "variants": variants}

result = query_clinvar("RS_ID_PLACEHOLDER")
os.makedirs("/workspace/raw", exist_ok=True)
with open("/workspace/raw/clinvar.json", "w") as f:
    json.dump(result, f, indent=2)
print(json.dumps(result, indent=2))
```
"""
