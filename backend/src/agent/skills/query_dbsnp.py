QUERY_DBSNP_SKILL = r"""
---
name: query-dbsnp
description: Query NCBI dbSNP Variation Services API for variant type, allele frequencies, and associated genes
---
# dbSNP Query Skill

Uses the NCBI Variation Services REST API (v0). Replace RS_ID_PLACEHOLDER with actual rsID.

## Python Code

```python
import requests, json, os

def query_dbsnp(rs_id: str) -> dict:
    rs_num = rs_id.lstrip("rRsS")
    resp = requests.get(
        f"https://api.ncbi.nlm.nih.gov/variation/v0/beta/refsnp/{rs_num}",
        headers={"Accept": "application/json"},
        timeout=15,
    )
    if resp.status_code != 200:
        return {"rs_id": rs_id, "found": False, "error": f"HTTP {resp.status_code}"}

    data = resp.json()
    primary = data.get("primary_snapshot_data", {})
    allele_annotations = primary.get("allele_annotations", [])

    genes = []
    for ann in allele_annotations:
        for assembly_ann in ann.get("assembly_annotation", []):
            for gene in assembly_ann.get("genes", []):
                symbol = gene.get("locus", "")
                if symbol and symbol not in [g["symbol"] for g in genes]:
                    genes.append({"symbol": symbol, "id": gene.get("id", 0)})

    frequencies = []
    for ann in allele_annotations:
        for freq in ann.get("frequency", []):
            total = freq.get("total_count", 0)
            count = freq.get("allele_count", 0)
            frequencies.append({
                "study": freq.get("study_name", ""),
                "allele": freq.get("observation", {}).get("deleted_sequence", ""),
                "frequency": round(count / total, 6) if total else None,
            })

    return {
        "rs_id": rs_id,
        "found": True,
        "variant_type": primary.get("variant_type", ""),
        "genes": genes[:5],
        "allele_frequencies": frequencies[:10],
    }

result = query_dbsnp("RS_ID_PLACEHOLDER")
os.makedirs("/workspace/raw", exist_ok=True)
with open("/workspace/raw/dbsnp.json", "w") as f:
    json.dump(result, f, indent=2)
print(json.dumps(result, indent=2))
```
"""
