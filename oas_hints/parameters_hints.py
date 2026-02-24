"""
Hint extractor for OAS parameters.

Collects parameters from both path-item level and operation level across
all paths. Covers: naming, location rules, descriptions, schema presence,
deprecated usage, and common mistakes.
"""
import re
from .models import Hint, Severity, SectionPayload

SECTION = "parameters"
HTTP_METHODS = ["get", "post", "put", "patch", "delete", "options", "head", "trace"]

# Standard header names that should NOT be used as custom parameters
FORBIDDEN_HEADERS = {
    "accept", "content-type", "authorization",
    "content-length", "transfer-encoding", "host"
}


def _check_parameter(
    param: dict,
    location: str,
    hints: list[Hint]
) -> None:
    """Check a single parameter object and append hints."""
    name: str = param.get("name", "")
    param_in: str = param.get("in", "")   # query, path, header, cookie
    required: bool = param.get("required", False)
    description: str = param.get("description", "")
    schema: dict = param.get("schema", {})
    deprecated: bool = param.get("deprecated", False)
    allow_empty: bool = param.get("allowEmptyValue", False)

    # ── Name ──────────────────────────────────────────────────────────────────
    if not name:
        hints.append(Hint(section=SECTION, location=location, severity=Severity.ERROR,
                           message="parameter is missing a name"))

    # ── In ────────────────────────────────────────────────────────────────────
    valid_in = {"query", "path", "header", "cookie"}
    if not param_in:
        hints.append(Hint(section=SECTION, location=location, severity=Severity.ERROR,
                           message=f"parameter '{name}' is missing the 'in' field"))
    elif param_in not in valid_in:
        hints.append(Hint(section=SECTION, location=location, severity=Severity.ERROR,
                           message=f"parameter '{name}' has invalid 'in' value '{param_in}' — must be one of {sorted(valid_in)}"))

    # ── Path params must be required ──────────────────────────────────────────
    if param_in == "path" and not required:
        hints.append(Hint(section=SECTION, location=location, severity=Severity.ERROR,
                           message=f"path parameter '{name}' must have required: true per OAS specification"))

    # ── Forbidden header names ─────────────────────────────────────────────────
    if param_in == "header" and name.lower() in FORBIDDEN_HEADERS:
        hints.append(Hint(section=SECTION, location=location, severity=Severity.ERROR,
                           message=f"header parameter '{name}' is a reserved HTTP header and must not be used as a custom parameter"))

    # ── Description ───────────────────────────────────────────────────────────
    if not description:
        hints.append(Hint(section=SECTION, location=location, severity=Severity.WARNING,
                           message=f"parameter '{name}' has no description"))

    # ── Schema ────────────────────────────────────────────────────────────────
    if not schema and "content" not in param:
        hints.append(Hint(section=SECTION, location=location, severity=Severity.ERROR,
                           message=f"parameter '{name}' has neither a schema nor a content object"))
    elif schema:
        schema_type = schema.get("type")

        if not schema_type and not any(k in schema for k in ("allOf", "anyOf", "oneOf", "$ref")):
            hints.append(Hint(section=SECTION, location=location, severity=Severity.WARNING,
                               message=f"parameter '{name}' schema has no type defined"))

        # Arrays need items
        if schema_type == "array" and "items" not in schema:
            hints.append(Hint(section=SECTION, location=location, severity=Severity.ERROR,
                               message=f"parameter '{name}' is array type but items is not defined"))

        # Objects as query params are unusual
        if param_in == "query" and schema_type == "object":
            hints.append(Hint(section=SECTION, location=location, severity=Severity.WARNING,
                               message=f"query parameter '{name}' has type: object — this may not serialise well; consider flattening"))

        # Enums
        enum_values = schema.get("enum")
        if enum_values is not None:
            if len(enum_values) == 0:
                hints.append(Hint(section=SECTION, location=location, severity=Severity.ERROR,
                                   message=f"parameter '{name}' enum is empty"))
            if len(enum_values) != len(set(str(v) for v in enum_values)):
                hints.append(Hint(section=SECTION, location=location, severity=Severity.WARNING,
                                   message=f"parameter '{name}' enum contains duplicate values"))

        # String constraints
        if schema_type == "string" and param_in == "query":
            if "maxLength" not in schema and "enum" not in schema and "format" not in schema:
                hints.append(Hint(section=SECTION, location=location, severity=Severity.INFO,
                                   message=f"query parameter '{name}' is an unconstrained string — consider maxLength or enum"))

    # ── Naming style ──────────────────────────────────────────────────────────
    if name:
        if param_in == "query":
            # Query params are commonly camelCase or snake_case — flag mixed signals
            if re.search(r"[\s]", name):
                hints.append(Hint(section=SECTION, location=location, severity=Severity.ERROR,
                                   message=f"query parameter name '{name}' contains whitespace"))
            if "-" in name:
                hints.append(Hint(section=SECTION, location=location, severity=Severity.WARNING,
                                   message=f"query parameter name '{name}' uses hyphens — may cause issues in some clients"))

        if param_in == "header":
            # Header names should be kebab-case by convention (case-insensitive in HTTP/2)
            if "_" in name:
                hints.append(Hint(section=SECTION, location=location, severity=Severity.INFO,
                                   message=f"header parameter '{name}' uses underscores — HTTP convention prefers kebab-case"))

    # ── Deprecated ────────────────────────────────────────────────────────────
    if deprecated:
        hints.append(Hint(section=SECTION, location=location, severity=Severity.INFO,
                           message=f"parameter '{name}' is marked deprecated"))

    # ── allowEmptyValue ───────────────────────────────────────────────────────
    if allow_empty and param_in not in ("query", ""):
        hints.append(Hint(section=SECTION, location=location, severity=Severity.WARNING,
                           message=f"allowEmptyValue is only valid for query parameters, not '{param_in}'"))


def extract_parameters_hints(spec: dict) -> SectionPayload:
    """
    Extract hints from all parameters across all paths and operations,
    plus any reusable parameters in components/parameters.

    Args:
        spec: Fully resolved OAS spec as a plain dict.

    Returns:
        SectionPayload with parameter hints and list of parameter entry dicts.
    """
    hints: list[Hint] = []
    raw_data: list[dict] = []

    # ── Reusable parameters in components ────────────────────────────────────
    for param_name, param in spec.get("components", {}).get("parameters", {}).items():
        loc = f"components.parameters.{param_name}"
        raw_data.append({"path": None, "method": None, "scope": "component", "parameter": param})
        _check_parameter(param, loc, hints)

    # ── Inline parameters across all paths and operations ────────────────────
    for path, path_item in spec.get("paths", {}).items():

        # Path-level parameters
        for i, param in enumerate(path_item.get("parameters", [])):
            loc = f"paths.{path}.parameters[{i}]"
            raw_data.append({"path": path, "method": None, "scope": "path-level", "parameter": param})
            _check_parameter(param, loc, hints)

        # Operation-level parameters
        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if not operation:
                continue
            for i, param in enumerate(operation.get("parameters", [])):
                loc = f"paths.{path}.{method}.parameters[{i}]"
                raw_data.append({"path": path, "method": method, "scope": "operation-level", "parameter": param})
                _check_parameter(param, loc, hints)

    if not raw_data:
        hints.append(Hint(
            section=SECTION, location="parameters",
            severity=Severity.INFO,
            message="no parameters found anywhere in the spec",
            raw={}
        ))

    return SectionPayload(section=SECTION, hints=hints, raw_data=raw_data)
