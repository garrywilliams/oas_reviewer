"""
validation_models.py
====================
Pydantic v2 models for structured LLM validation responses.

These models serve three purposes:
  1. Define the JSON schema that is injected into each LLM prompt
  2. Parse and validate the LLM's response
  3. Act as Agno response models (pass directly as response_model=)

Each section prompt returns a SectionValidationResult.
The full report is assembled into a ValidationReport.
"""
from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


# ── Severity ──────────────────────────────────────────────────────────────────

class Severity(str, Enum):
    ERROR   = "error"    # Clear, unambiguous violation
    WARNING = "warning"  # Likely issue; may need context to confirm
    INFO    = "info"     # Advisory; not a violation per se


# ── Individual finding ────────────────────────────────────────────────────────

class Finding(BaseModel):
    """A single rule violation found by the LLM."""

    rule_id: str = Field(
        description=(
            "The canonical rule identifier in SCREAMING_SNAKE_CASE. "
            "Must be one of the rule IDs listed in the prompt's 'Canonical Rule IDs' section. "
            "Example: 'STRING_CONSTANT_MISSING'"
        )
    )
    section: str = Field(
        description=(
            "The OAS section this finding belongs to. "
            "One of: info, paths, operations, schemas, parameters"
        )
    )
    severity: Severity = Field(
        description="How serious the violation is: error, warning, or info"
    )
    pointer: str = Field(
        description=(
            "Dot-notation location of the violation within the OAS document. "
            "Example: 'components.schemas.UserRequest.properties.request_id'"
        )
    )
    message: str = Field(
        description=(
            "A concise, specific description of what is wrong. "
            "Do not repeat the rule_id or pointer here — just describe the issue."
        )
    )
    suggested_fix: str = Field(
        description=(
            "A concrete, actionable suggestion for how to fix this violation. "
            "Be specific — include example values or patterns where helpful."
        )
    )

    def label(self) -> str:
        """Formatted label used in display: [SECTION][RULE_ID]"""
        return f"[{self.section.upper()}][{self.rule_id}]"

    def full_description(self) -> str:
        """Single-string description matching your original format."""
        return f"{self.label()} {self.pointer} - {self.message}"


# ── Per-section result ────────────────────────────────────────────────────────

class SectionValidationResult(BaseModel):
    """
    The structured response returned by a single section prompt.
    This is the model you pass as response_model= to Agno.
    """

    section: str = Field(
        description="The OAS section that was validated: info, paths, operations, schemas, or parameters"
    )
    findings: list[Finding] = Field(
        default_factory=list,
        description=(
            "List of rule violations found. "
            "Empty list if no violations were found — do NOT omit this field."
        )
    )
    summary: str = Field(
        default="",
        description=(
            "A one or two sentence plain-English summary of the overall quality of this section. "
            "Mention the count of findings and any dominant patterns."
        )
    )

    @property
    def has_findings(self) -> bool:
        return len(self.findings) > 0

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.INFO)


# ── Full report (assembled from all section results) ─────────────────────────

class ValidationReport(BaseModel):
    """
    Complete validation report assembled from all section results.
    Built in Python after collecting all LLM responses — not returned by the LLM.
    """

    spec_title: str = Field(default="Unknown", description="Title from the OAS info.title field")
    spec_version: str = Field(default="Unknown", description="Version from the OAS info.version field")
    sections: dict[str, SectionValidationResult] = Field(
        default_factory=dict,
        description="Keyed by section name: info, paths, operations, schemas, parameters"
    )

    def add_section(self, result: SectionValidationResult) -> None:
        self.sections[result.section] = result

    @property
    def all_findings(self) -> list[Finding]:
        return [f for r in self.sections.values() for f in r.findings]

    @property
    def total_errors(self) -> int:
        return sum(r.error_count for r in self.sections.values())

    @property
    def total_warnings(self) -> int:
        return sum(r.warning_count for r in self.sections.values())

    @property
    def total_info(self) -> int:
        return sum(r.info_count for r in self.sections.values())
