from .generate_report import GENERATE_REPORT_SKILL
from .query_clinvar import QUERY_CLINVAR_SKILL
from .query_dbsnp import QUERY_DBSNP_SKILL
from .query_ensembl import QUERY_ENSEMBL_SKILL
from .query_gene import QUERY_GENE_SKILL
from .query_gnomad import QUERY_GNOMAD_SKILL
from .query_pubmed import QUERY_PUBMED_SKILL
from .query_uniprot import QUERY_UNIPROT_SKILL

# List of (skill_name, skill_md_content) tuples — order determines mounting order
ALL_SKILLS: list[tuple[str, str]] = [
    ("query-clinvar", QUERY_CLINVAR_SKILL),
    ("query-dbsnp", QUERY_DBSNP_SKILL),
    ("query-gnomad", QUERY_GNOMAD_SKILL),
    ("query-gene", QUERY_GENE_SKILL),
    ("query-uniprot", QUERY_UNIPROT_SKILL),
    ("query-pubmed", QUERY_PUBMED_SKILL),
    ("query-ensembl", QUERY_ENSEMBL_SKILL),
    ("generate-report", GENERATE_REPORT_SKILL),
]
