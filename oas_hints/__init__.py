"""
OAS Hint Extractors
===================
Pre-processing utilities that convert a resolved OAS 3.x spec into
structured hints for LLM prompt construction.

Usage
-----
    from oas_hints import extract_all_hints, SectionPayload

    hints_by_section = extract_all_hints(resolved_spec)

    for section_name, payload in hints_by_section.items():
        print(f"\\n{'='*60}")
        print(f"SECTION: {section_name.upper()}")
        print(payload.hints_block())
"""

from .models import Hint, Severity, SectionPayload
from .info_hints import extract_info_hints
from .paths_hints import extract_paths_hints
from .operations_hints import extract_operations_hints
from .schemas_hints import extract_schemas_hints
from .parameters_hints import extract_parameters_hints


def extract_all_hints(spec: dict) -> dict[str, SectionPayload]:
    """
    Run all hint extractors against a fully resolved OAS spec.

    Args:
        spec: Fully resolved OAS spec dict (e.g. from prance or jsonref).

    Returns:
        Ordered dict mapping section name → SectionPayload.
        Sections: "info", "paths", "operations", "schemas", "parameters"
    """
    return {
        "info":       extract_info_hints(spec),
        "paths":      extract_paths_hints(spec),
        "operations": extract_operations_hints(spec),
        "schemas":    extract_schemas_hints(spec),
        "parameters": extract_parameters_hints(spec),
    }


__all__ = [
    "Hint",
    "Severity",
    "SectionPayload",
    "extract_info_hints",
    "extract_paths_hints",
    "extract_operations_hints",
    "extract_schemas_hints",
    "extract_parameters_hints",
    "extract_all_hints",
]
