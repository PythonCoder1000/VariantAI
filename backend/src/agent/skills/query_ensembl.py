QUERY_ENSEMBL_SKILL = r"""
---
name: query-ensembl
description: Query Ensembl REST API for variant consequence type and VEP predictions (SIFT, PolyPhen) for a canonical transcript
---
# Ensembl Query Skill

Two calls: variation endpoint for basic data, VEP endpoint for functional predictions.
Replace RS_ID_PLACEHOLDER with the actual rsID.

## Python Code

```python
import requests, json, os

HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

def query_ensembl(rs_id: str) -> dict:
    # Basic variant data
    var_resp = requests.get(
        f"https://rest.ensembl.org/variation/human/{rs_id}",
        headers=HEADERS,
        timeout=15,
    )
    if var_resp.status_code != 200:
        return {"rs_id": rs_id, "found": False, "error": f"HTTP {var_resp.status_code}"}

    var_data = var_resp.json()
    mappings = [
        {"location": m.get("location", ""), "allele_string": m.get("allele_string", ""),
         "assembly": m.get("assembly_name", "")}
        for m in var_data.get("mappings", [])[:3]
    ]

    # VEP functional predictions
    vep_resp = requests.get(
        f"https://rest.ensembl.org/vep/human/id/{rs_id}",
        headers=HEADERS,
        params={"SIFT": "b", "PolyPhen": "b", "canonical": 1},
        timeout=20,
    )

    predictions = []
    if vep_resp.status_code == 200:
        for entry in vep_resp.json()[:3]:
            for tc in entry.get("transcript_consequences", []):
                if tc.get("canonical"):
                    predictions.append({
                        "gene_symbol": tc.get("gene_symbol", ""),
                        "transcript": tc.get("transcript_id", ""),
                        "consequence": tc.get("consequence_terms", []),
                        "impact": tc.get("impact", ""),
                        "sift_score": tc.get("sift_score"),
                        "sift_prediction": tc.get("sift_prediction"),
                        "polyphen_score": tc.get("polyphen_score"),
                        "polyphen_prediction": tc.get("polyphen_prediction"),
                        "amino_acids": tc.get("amino_acids", ""),
                        "codons": tc.get("codons", ""),
                    })

    return {
        "rs_id": rs_id,
        "found": True,
        "most_severe_consequence": var_data.get("most_severe_consequence", ""),
        "source": var_data.get("source", ""),
        "mappings": mappings,
        "vep_predictions": predictions[:5],
    }

result = query_ensembl("RS_ID_PLACEHOLDER")
os.makedirs("/workspace/raw", exist_ok=True)
with open("/workspace/raw/ensembl.json", "w") as f:
    json.dump(result, f, indent=2)
print(json.dumps(result, indent=2))
```
"""
