"""
Hint extractor for OAS component schemas.

Covers: naming conventions, required fields, property descriptions,
enum definitions, type completeness, and composition keywords.
"""
import re
from .models import Hint, Severity, SectionPayload

SECTION = "schemas"

# Primitive types valid in OAS 3.x
OAS_PRIMITIVE_TYPES = {"string", "number", "integer", "boolean", "array", "object"}


def _check_schema(
    schema: dict,
    location: str,
    hints: list[Hint],
    depth: int = 0
) -> None:
    """
    Recursively check a schema object and append hints.
    depth guards against infinite recursion on deeply nested schemas.
    """
    if depth > 10 or not isinstance(schema, dict):
        return

    schema_type = schema.get("type")
    properties: dict = schema.get("properties", {})
    required_fields: list = schema.get("required", [])
    description = schema.get("description", "")

    # ── Type ──────────────────────────────────────────────────────────────────
    if schema_type and schema_type not in OAS_PRIMITIVE_TYPES:
        hints.append(Hint(section=SECTION, location=location, severity=Severity.ERROR,
                           message=f"unknown type '{schema_type}' — must be one of {sorted(OAS_PRIMITIVE_TYPES)}"))

    if not schema_type and not any(k in schema for k in ("allOf", "anyOf", "oneOf", "$ref", "not")):
        if properties:
            # Has properties but no type — common omission
            hints.append(Hint(section=SECTION, location=location, severity=Severity.WARNING,
                               message="schema has properties but no type declared — consider adding type: object"))
        elif schema:
            hints.append(Hint(section=SECTION, location=location, severity=Severity.INFO,
                               message="schema has no type and no composition keyword"))

    # ── Description ───────────────────────────────────────────────────────────
    if not description:
        hints.append(Hint(section=SECTION, location=location, severity=Severity.WARNING,
                           message="schema has no description"))

    # ── Properties ───────────────────────────────────────────────────────────
    for prop_name, prop_schema in properties.items():
        prop_loc = f"{location}.properties.{prop_name}"

        if not isinstance(prop_schema, dict):
            continue

        # Property naming convention — flag anything that isn't camelCase or snake_case
        if re.search(r"[\s\-]", prop_name):
            hints.append(Hint(section=SECTION, location=prop_loc, severity=Severity.WARNING,
                               message=f"property name '{prop_name}' contains spaces or hyphens"))

        if not prop_schema.get("description"):
            hints.append(Hint(section=SECTION, location=prop_loc, severity=Severity.WARNING,
                               message=f"property '{prop_name}' has no description"))

        prop_type = prop_schema.get("type")

        # String constraints
        if prop_type == "string":
            if "maxLength" not in prop_schema and "enum" not in prop_schema and "format" not in prop_schema:
                hints.append(Hint(section=SECTION, location=prop_loc, severity=Severity.INFO,
                                   message=f"string property '{prop_name}' has no maxLength, enum, or format constraint"))
            if "format" in prop_schema:
                known_formats = {
                    "date", "date-time", "password", "byte", "binary",
                    "email", "uuid", "uri", "hostname", "ipv4", "ipv6"
                }
                fmt = prop_schema["format"]
                if fmt not in known_formats:
                    hints.append(Hint(section=SECTION, location=prop_loc, severity=Severity.INFO,
                                       message=f"property '{prop_name}' uses non-standard format '{fmt}'"))

        # Integer/number constraints
        if prop_type in ("integer", "number"):
            if "minimum" not in prop_schema and "maximum" not in prop_schema:
                hints.append(Hint(section=SECTION, location=prop_loc, severity=Severity.INFO,
                                   message=f"numeric property '{prop_name}' has no minimum/maximum bounds"))

        # Array items
        if prop_type == "array" and "items" not in prop_schema:
            hints.append(Hint(section=SECTION, location=prop_loc, severity=Severity.ERROR,
                               message=f"array property '{prop_name}' is missing 'items' definition"))

        # Nullable handling (OAS 3.0 vs 3.1 differ here)
        if prop_schema.get("nullable") and prop_schema.get("type") == "null":
            hints.append(Hint(section=SECTION, location=prop_loc, severity=Severity.WARNING,
                               message=f"property '{prop_name}' uses both nullable:true and type:null — redundant"))

        # Recurse into nested object schemas
        if prop_type == "object" or prop_schema.get("properties"):
            _check_schema(prop_schema, prop_loc, hints, depth + 1)

    # ── Required fields ───────────────────────────────────────────────────────
    for req in required_fields:
        if req not in properties:
            hints.append(Hint(section=SECTION, location=location, severity=Severity.ERROR,
                               message=f"'{req}' is listed in required but not defined in properties"))

    # ── Enums ─────────────────────────────────────────────────────────────────
    enum_values = schema.get("enum")
    if enum_values is not None:
        if len(enum_values) == 0:
            hints.append(Hint(section=SECTION, location=location, severity=Severity.ERROR,
                               message="enum is defined but empty"))
        if len(enum_values) != len(set(str(v) for v in enum_values)):
            hints.append(Hint(section=SECTION, location=location, severity=Severity.WARNING,
                               message="enum contains duplicate values"))

    # ── Composition ───────────────────────────────────────────────────────────
    for keyword in ("allOf", "anyOf", "oneOf"):
        composition = schema.get(keyword, [])
        for i, sub_schema in enumerate(composition):
            _check_schema(sub_schema, f"{location}.{keyword}[{i}]", hints, depth + 1)

    if "allOf" in schema and "properties" in schema:
        hints.append(Hint(section=SECTION, location=location, severity=Severity.INFO,
                           message="schema uses allOf alongside top-level properties — ensure this is intentional and not a modelling error"))


def extract_schemas_hints(spec: dict) -> SectionPayload:
    """
    Extract hints from all schemas in components/schemas.

    Args:
        spec: Fully resolved OAS spec as a plain dict.

    Returns:
        SectionPayload with schema hints and list of schema entry dicts.
    """
    schemas: dict = spec.get("components", {}).get("schemas", {})
    hints: list[Hint] = []
    raw_data: list[dict] = []

    if not schemas:
        hints.append(Hint(
            section=SECTION, location="components.schemas",
            severity=Severity.INFO,
            message="no schemas defined in components/schemas",
            raw={}
        ))
        return SectionPayload(section=SECTION, hints=hints, raw_data=raw_data)

    for schema_name, schema in schemas.items():
        loc = f"components.schemas.{schema_name}"
        raw_data.append({"name": schema_name, "schema": schema})

        # ── Naming convention ─────────────────────────────────────────────────
        if not re.match(r"^[A-Z][a-zA-Z0-9]*$", schema_name):
            hints.append(Hint(section=SECTION, location=loc, severity=Severity.WARNING,
                               message=f"schema name '{schema_name}' does not follow PascalCase convention"))

        _check_schema(schema, loc, hints)

    return SectionPayload(section=SECTION, hints=hints, raw_data=raw_data)
