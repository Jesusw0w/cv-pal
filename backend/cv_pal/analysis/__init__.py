"""Deterministic CV analysis.

Everything here is a pure function over text: the same inputs always give the same
report, with no model, no network and no cost. This is the *deterministic first*
principle in practice — parseability, keyword coverage and gap analysis are the bulk of
the product's value, and none of it needs an LLM configured.
"""

from cv_pal.analysis.keywords import (
    CoverageReport,
    Keyword,
    analyse,
    coverage,
    extract_keywords,
)
from cv_pal.analysis.parseability import ParseabilityReport, check_parseability

__all__ = [
    "CoverageReport",
    "Keyword",
    "ParseabilityReport",
    "analyse",
    "check_parseability",
    "coverage",
    "extract_keywords",
]
