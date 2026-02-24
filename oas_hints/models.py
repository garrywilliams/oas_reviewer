from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class Hint:
    """A single pre-digested observation about the OAS document."""
    section: str          # e.g. "info", "paths", "operations", "schemas", "parameters"
    location: str         # dot-notation path e.g. "paths./users.get"
    severity: Severity
    message: str
    raw: dict = field(default_factory=dict, repr=False)  # the raw OAS fragment this hint describes

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.location} — {self.message}"


@dataclass
class SectionPayload:
    """Everything needed to build a prompt for one logical section."""
    section: str
    hints: list[Hint]
    raw_data: list[dict] | dict

    def hints_block(self) -> str:
        """Formatted hint block ready to embed in a prompt."""
        if not self.hints:
            return "(no pre-flight observations)"
        return "\n".join(str(h) for h in self.hints)
