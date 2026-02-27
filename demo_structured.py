"""
demo_structured.py
==================
Demonstrates the full structured-output pipeline:

  1. Load OAS string → resolve → extract hints
  2. Build section prompts (showing what goes to the LLM)
  3. Simulate LLM JSON responses (so this runs without Azure credentials)
  4. Parse responses into SectionValidationResult via Pydantic
  5. Assemble into ValidationReport
  6. Render to HTML

To wire in real Azure calls, replace _simulate_llm_response() with
call_llm_for_section() from llm_caller.py.
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
from oas_hints.loader import load_oas_string
from oas_hints import extract_all_hints
from oas_hints.prompt_builder import build_section_prompt
from oas_hints.validation_models import (
    SectionValidationResult, ValidationReport, Finding, Severity
)
from oas_hints.html_renderer import render_report


# ── Sample spec ───────────────────────────────────────────────────────────────

SAMPLE_SPEC = """
openapi: "3.0.3"
info:
  title: my example api
  version: "not-semver"
  contact:
    name: Platform Team

paths:
  /Users:
    get:
      summary: "get users."
      responses:
        "200":
          description: Success

  /users/{userId}:
    get:
      operationId: getUser
      summary: Retrieve a user by ID
      tags: [Users]
      parameters:
        - name: userId
          in: path
          required: true
          description: The unique identifier
          schema:
            type: integer
      responses:
        "200":
          description: User found

  /users/{userId}/orders:
    get:
      operationId: getUserOrders
      tags: [Users]
      parameters:
        - name: userId
          in: path
          description: User ID
          schema:
            type: integer
        - name: status
          in: query
          description: Filter by status
          schema:
            type: string
      responses:
        "200":
          description: List of orders

components:
  schemas:
    User:
      type: object
      description: A user account
      required: [id, email, nonExistentField]
      properties:
        id:
          type: integer
          description: Unique user ID
        email:
          type: string
          format: email
          description: Email address
        username:
          type: string
        tags:
          type: array

    order_response:
      type: object
      properties:
        orderId:
          type: integer
        amount:
          type: number
"""

# ── Section rule configuration ────────────────────────────────────────────────
# In your real code this comes from your rule definitions

SECTION_RULES = {
    "info": {
        "focus": [
            "title must be in Title Case",
            "version must follow semantic versioning (major.minor.patch)",
            "description must be present and meaningful",
            "contact object must include an email address",
        ],
        "rule_ids": [
            "TITLE_CASING",
            "TITLE_FORBIDDEN_WORD",
            "VERSION_FORMAT",
            "DESCRIPTION_MISSING",
            "CONTACT_MISSING",
            "CONTACT_EMAIL_MISSING",
        ],
    },
    "parameters": {
        "focus": [
            "path parameters must declare required: true",
            "all parameters must have a description",
            "query string parameters should have constraints (maxLength, enum, or format)",
            "parameter names should follow consistent casing convention",
        ],
        "rule_ids": [
            "PATH_PARAM_NOT_REQUIRED",
            "DESCRIPTION_MISSING",
            "STRING_UNCONSTRAINED",
            "NAMING_CONVENTION",
            "FORBIDDEN_HEADER",
            "ARRAY_ITEMS_MISSING",
        ],
    },
    "schemas": {
        "focus": [
            "schema names must be PascalCase",
            "all schemas and properties must have descriptions",
            "array properties must define items",
            "required fields must be defined in properties",
            "string properties should have format, enum, or maxLength",
        ],
        "rule_ids": [
            "SCHEMA_NAMING_CONVENTION",
            "DESCRIPTION_MISSING",
            "ARRAY_ITEMS_MISSING",
            "REQUIRED_FIELD_UNDEFINED",
            "STRING_UNCONSTRAINED",
            "NUMERIC_UNCONSTRAINED",
        ],
    },
    "operations": {
        "focus": [
            "every operation must have a unique operationId",
            "summary must start with a capital letter and not end with a period",
            "every operation must have at least one tag",
            "operations must define error response codes (4xx or default)",
        ],
        "rule_ids": [
            "OPERATION_ID_MISSING",
            "OPERATION_ID_DUPLICATE",
            "SUMMARY_CASING",
            "SUMMARY_TRAILING_PERIOD",
            "TAG_MISSING",
            "ERROR_RESPONSE_MISSING",
        ],
    },
    "paths": {
        "focus": [
            "path segments should be lowercase kebab-case",
            "trailing slash usage must be consistent",
            "path parameters declared in template must be defined",
        ],
        "rule_ids": [
            "PATH_CASING",
            "TRAILING_SLASH_INCONSISTENT",
            "PATH_PARAM_UNDEFINED",
            "PATH_PARAM_UNDECLARED",
        ],
    },
}


# ── Simulated LLM responses ───────────────────────────────────────────────────
# Represents what Azure GPT-4.1 would return for each section prompt.
# Replace this function with call_llm_for_section() for real operation.

def _simulate_llm_response(section: str) -> dict:
    """Return a plausible structured response for each section."""
    responses = {
        "info": {
            "section": "info",
            "summary": "The info section has two clear violations: the title is not in Title Case and the version does not follow semantic versioning. The contact object is present but lacks an email address.",
            "findings": [
                {
                    "rule_id": "TITLE_CASING",
                    "section": "info",
                    "severity": "error",
                    "pointer": "info.title",
                    "message": "Title 'my example api' is entirely lowercase and does not follow Title Case convention.",
                    "suggested_fix": "Rename to 'My Example API' — capitalise each significant word and use uppercase for acronyms."
                },
                {
                    "rule_id": "VERSION_FORMAT",
                    "section": "info",
                    "severity": "error",
                    "pointer": "info.version",
                    "message": "Version 'not-semver' does not follow semantic versioning.",
                    "suggested_fix": "Use a semver string such as '1.0.0' following major.minor.patch format."
                },
                {
                    "rule_id": "CONTACT_EMAIL_MISSING",
                    "section": "info",
                    "severity": "warning",
                    "pointer": "info.contact",
                    "message": "Contact object is present but contains no email address.",
                    "suggested_fix": "Add an email field, e.g. email: platform-team@example.com"
                },
            ]
        },
        "parameters": {
            "section": "parameters",
            "summary": "One path parameter is missing required:true, and one query parameter is an unconstrained string. Two parameters are missing descriptions.",
            "findings": [
                {
                    "rule_id": "PATH_PARAM_NOT_REQUIRED",
                    "section": "parameters",
                    "severity": "error",
                    "pointer": "paths./users/{userId}/orders.get.parameters[0]",
                    "message": "Path parameter 'userId' does not declare required: true, which is mandatory for path parameters per the OAS specification.",
                    "suggested_fix": "Add 'required: true' to the userId parameter definition under /users/{userId}/orders GET."
                },
                {
                    "rule_id": "STRING_UNCONSTRAINED",
                    "section": "parameters",
                    "severity": "info",
                    "pointer": "paths./users/{userId}/orders.get.parameters[1]",
                    "message": "Query parameter 'status' is a plain string with no enum, format, or maxLength constraint.",
                    "suggested_fix": "Add an enum to restrict valid values, e.g. enum: [pending, shipped, delivered, cancelled]"
                },
            ]
        },
        "schemas": {
            "section": "schemas",
            "summary": "Several schema quality issues were found: a missing items definition on an array property, a required field that does not exist in properties, a non-PascalCase schema name, and missing descriptions.",
            "findings": [
                {
                    "rule_id": "ARRAY_ITEMS_MISSING",
                    "section": "schemas",
                    "severity": "error",
                    "pointer": "components.schemas.User.properties.tags",
                    "message": "Property 'tags' is declared as type array but has no items definition.",
                    "suggested_fix": "Add an items schema, e.g. items: { type: string } or reference a component schema."
                },
                {
                    "rule_id": "REQUIRED_FIELD_UNDEFINED",
                    "section": "schemas",
                    "severity": "error",
                    "pointer": "components.schemas.User",
                    "message": "'nonExistentField' is listed in required but is not defined in properties.",
                    "suggested_fix": "Either add a 'nonExistentField' property definition or remove it from the required array."
                },
                {
                    "rule_id": "SCHEMA_NAMING_CONVENTION",
                    "section": "schemas",
                    "severity": "warning",
                    "pointer": "components.schemas.order_response",
                    "message": "Schema name 'order_response' uses snake_case instead of PascalCase.",
                    "suggested_fix": "Rename to 'OrderResponse' to follow PascalCase convention."
                },
                {
                    "rule_id": "DESCRIPTION_MISSING",
                    "section": "schemas",
                    "severity": "warning",
                    "pointer": "components.schemas.User.properties.username",
                    "message": "Property 'username' has no description.",
                    "suggested_fix": "Add a description, e.g. description: 'The user's chosen display name, unique across the platform.'"
                },
            ]
        },
        "operations": {
            "section": "operations",
            "summary": "The GET /Users operation is missing an operationId and its summary has quality issues. Two operations lack error response definitions.",
            "findings": [
                {
                    "rule_id": "OPERATION_ID_MISSING",
                    "section": "operations",
                    "severity": "error",
                    "pointer": "paths./Users.get",
                    "message": "Operation has no operationId — this is required for SDK generation and API tooling.",
                    "suggested_fix": "Add operationId: listUsers (or similar verb-noun convention matching your codebase)."
                },
                {
                    "rule_id": "SUMMARY_CASING",
                    "section": "operations",
                    "severity": "warning",
                    "pointer": "paths./Users.get.summary",
                    "message": "Summary 'get users.' starts with a lowercase letter.",
                    "suggested_fix": "Capitalise to 'Get users' and remove the trailing period."
                },
                {
                    "rule_id": "SUMMARY_TRAILING_PERIOD",
                    "section": "operations",
                    "severity": "info",
                    "pointer": "paths./Users.get.summary",
                    "message": "Summary ends with a period, which is contrary to convention for short summaries.",
                    "suggested_fix": "Remove the trailing period: change 'get users.' to 'Get users'."
                },
            ]
        },
        "paths": {
            "section": "paths",
            "summary": "One path uses an uppercase segment which violates kebab-case convention.",
            "findings": [
                {
                    "rule_id": "PATH_CASING",
                    "section": "paths",
                    "severity": "warning",
                    "pointer": "paths./Users",
                    "message": "Path '/Users' contains an uppercase character in a static segment.",
                    "suggested_fix": "Rename to '/users' — all static path segments should be lowercase."
                },
            ]
        }
    }
    return responses.get(section, {"section": section, "findings": [], "summary": "No findings."})


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_pipeline():
    print("=" * 70)
    print("STRUCTURED OUTPUT PIPELINE DEMO")
    print("=" * 70)

    # 1. Load and resolve spec
    spec, load_errors = load_oas_string(SAMPLE_SPEC)
    if load_errors:
        for e in load_errors:
            print(f"  LOAD WARNING: {e}")
    if spec is None:
        print("Spec load failed — aborting")
        return

    # 2. Extract hints for all sections
    all_hints = extract_all_hints(spec)

    # 3. Build a report container
    report = ValidationReport(
        spec_title=spec.get("info", {}).get("title", "Unknown"),
        spec_version=str(spec.get("info", {}).get("version", "Unknown")),
    )

    # 4. For each section: build prompt → call LLM → parse → add to report
    for section_name, payload in all_hints.items():
        rules = SECTION_RULES.get(section_name, {})

        # Build the prompt
        prompt = build_section_prompt(
            payload=payload,
            validation_focus=rules.get("focus", []),
            canonical_rule_ids=rules.get("rule_ids", []),
        )

        # Show a snippet of the prompt for the first section
        if section_name == "parameters":
            print(f"\n{'─'*70}")
            print(f"SAMPLE PROMPT SNIPPET ({section_name.upper()}):")
            print(f"{'─'*70}")
            print(prompt[:800] + "\n... [truncated]")

        # Call LLM (simulated here — replace with call_llm_for_section())
        raw_response = _simulate_llm_response(section_name)

        # Parse via Pydantic
        result = SectionValidationResult.model_validate(raw_response)
        report.add_section(result)

        print(f"\n  ✓ {section_name:12s}  {result.error_count}E  {result.warning_count}W  {result.info_count}I  — {len(result.findings)} findings")

    # 5. Render to HTML
    html = render_report(report)

    output_path = "/mnt/user-data/outputs/validation_report.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n{'='*70}")
    print(f"Report written to: {output_path}")
    print(f"Total findings: {len(report.all_findings)}  ({report.total_errors}E / {report.total_warnings}W / {report.total_info}I)")

    # 6. Show what the structured JSON looks like for one section
    print(f"\n{'─'*70}")
    print("STRUCTURED JSON (parameters section — as returned by LLM):")
    print(f"{'─'*70}")
    params_result = report.sections.get("parameters")
    if params_result:
        print(json.dumps(params_result.model_dump(), indent=2))


if __name__ == "__main__":
    run_pipeline()
