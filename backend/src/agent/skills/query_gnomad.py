QUERY_GNOMAD_SKILL = r'''
---
name: query-gnomad
description: Query gnomAD v4 GraphQL API for population allele frequencies across 140k+ exomes and genomes
---
# gnomAD Query Skill

Two-step: search by rsID to get variant_id, then fetch detailed frequency data.
Replace RS_ID_PLACEHOLDER with the actual rsID.

## Python Code

```python
import requests, json, os

GNOMAD_API = "https://gnomad.broadinstitute.org/api"

def query_gnomad(rs_id: str) -> dict:
    search_query = """
    query SearchVariants($query: String!, $dataset: DatasetId!) {
      variant_search(query: $query, dataset: $dataset) {
        variant_id
        rsids
      }
    }
    """
    search_resp = requests.post(
        GNOMAD_API,
        json={"query": search_query, "variables": {"query": rs_id, "dataset": "gnomad_r4"}},
        timeout=20,
    )
    if search_resp.status_code != 200:
        return {"rs_id": rs_id, "found": False, "error": f"HTTP {search_resp.status_code}"}

    search_results = search_resp.json().get("data", {}).get("variant_search", [])
    if not search_results:
        return {"rs_id": rs_id, "found": False, "message": "Not found in gnomAD v4"}

    variant_id = search_results[0]["variant_id"]

    detail_query = """
    query VariantDetails($variantId: String!, $dataset: DatasetId!) {
      variant(variantId: $variantId, dataset: $dataset) {
        variant_id
        rsids
        genome { ac an af homozygote_count populations { id ac an af } }
        exome  { ac an af homozygote_count }
        consequence
        in_silico_predictors { id value flags }
      }
    }
    """
    detail_resp = requests.post(
        GNOMAD_API,
        json={"query": detail_query, "variables": {"variantId": variant_id, "dataset": "gnomad_r4"}},
        timeout=20,
    )
    if detail_resp.status_code != 200:
        return {"rs_id": rs_id, "variant_id": variant_id, "found": True, "error": "Detail query failed"}

    detail = detail_resp.json().get("data", {}).get("variant", {})
    return {
        "rs_id": rs_id,
        "variant_id": variant_id,
        "found": True,
        "genome": detail.get("genome"),
        "exome": detail.get("exome"),
        "consequence": detail.get("consequence"),
        "in_silico_predictors": detail.get("in_silico_predictors", []),
    }

result = query_gnomad("RS_ID_PLACEHOLDER")
os.makedirs("/workspace/raw", exist_ok=True)
with open("/workspace/raw/gnomad.json", "w") as f:
    json.dump(result, f, indent=2)
print(json.dumps(result, indent=2))
```
'''
