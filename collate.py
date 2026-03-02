"""
collate.py
==========
Collates SectionValidationResult responses from parallel LLM calls
and renders them to an HTML report.

Assumes all LLM responses are valid SectionValidationResult models.
"""

from oas_hints.validation_models import SectionValidationResult, ValidationReport
from oas_hints.html_renderer import render_report


def collate_results(
    spec: dict,
    keys: tuple,
    results: dict[str, SectionValidationResult],
) -> str:
    """
    Assemble SectionValidationResult responses into an HTML report.

    Args:
        spec:    Resolved OAS spec dict (for title and version).
        keys:    Your original ordered keys tuple e.g. ("correlation", "parameters", ...)
                 Used to render sections in a consistent order regardless of
                 which parallel future completed first.
        results: Dict of group name → SectionValidationResult
                 from your as_completed() loop.

    Returns:
        HTML report string.
    """
    report = ValidationReport(
        spec_title=spec.get("info", {}).get("title", "Unknown"),
        spec_version=str(spec.get("info", {}).get("version", "Unknown")),
    )

    for key in keys:
        if key in results:
            report.add_section(results[key])

    return render_report(report)
