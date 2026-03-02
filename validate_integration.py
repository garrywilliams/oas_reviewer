"""
validate_integration.py
=======================
Shows how to integrate the OAS hints toolkit into your existing validate.py.

Your existing structure (from validate.py) is preserved exactly:
  - prompts dict with rule group keys
  - fmt_prompt() call per group
  - agent.run() per group

Only three things change:
  1. Hint variables come from the toolkit extractors instead of your pre-processing
  2. Raw data (the OAS fragments) comes from payload.raw_data
  3. Response is parsed as SectionValidationResult JSON instead of HTML rows
"""

import json
from oas_hints.loader import load_oas_string
from oas_hints import extract_all_hints
from oas_hints.validation_models import SectionValidationResult, ValidationReport
from oas_hints.html_renderer import render_report


def validate_endpoint(spec_content: str, YOUR_RULES: dict, agent) -> str:
    """
    Drop-in replacement for your existing validate_endpoint function.

    Args:
        spec_content: Raw OAS YAML or JSON string
        YOUR_RULES:   Your existing rule group config (focus + canonical_rule_ids)
        agent:        Your configured Agno agent with response_model=SectionValidationResult

    Returns:
        HTML report string
    """

    # ── Step 1: Load and resolve spec ─────────────────────────────────────────
    spec, errors = load_oas_string(spec_content)
    if spec is None:
        raise ValueError(f"Could not load spec: {errors}")

    # ── Step 2: Run all hint extractors ───────────────────────────────────────
    all_hints = extract_all_hints(spec)

    # ── Step 3: Map to your existing variable names ───────────────────────────
    # These replace whatever your pre-processing step currently generates.
    # The variable names match what your fmt_prompt() calls already expect.

    HINT_PARAMETERS = all_hints["parameters"].hints_block()
    HINT_SCHEMAS    = all_hints["schemas"].hints_block()
    HINT_OPERATIONS = all_hints["operations"].hints_block()
    HINT_PATHS      = all_hints["paths"].hints_block()
    INFO_TITLE      = spec.get("info", {}).get("title", "")

    # Raw OAS fragments — passed as context to the LLM
    parameters_list = json.dumps(all_hints["parameters"].raw_data, indent=2)
    schemas_list    = json.dumps(all_hints["schemas"].raw_data,    indent=2)
    operations_list = json.dumps(all_hints["operations"].raw_data, indent=2)
    paths_list      = json.dumps(all_hints["paths"].raw_data,      indent=2)

    # ── Step 4: Build prompts — your existing structure, unchanged ────────────
    # This mirrors your existing prompts dict in validate.py exactly.
    # fmt_prompt() is your existing function — not changed.

    prompts = {
        "correlation": fmt_prompt(
            OAS_CORRELATION_PROMPT,
            HINT_OPERATIONS=HINT_OPERATIONS,
            HINT_SCHEMAS=HINT_SCHEMAS,
            HINT_PARAMETERS=HINT_PARAMETERS,
            OAS_PARAMETERS=parameters_list,    # raw data added
        ),
        "parameters": fmt_prompt(
            OAS_PARAMETERS_PROMPT,
            HINT_OPERATIONS=HINT_OPERATIONS,
            HINT_SCHEMAS=HINT_SCHEMAS,
            HINT_PARAMETERS=HINT_PARAMETERS,
            OAS_PARAMETERS=parameters_list,    # raw data added
        ),
        "reqresp": fmt_prompt(
            OAS_REQRESP_PROMPT,
            HINT_OPERATIONS=HINT_OPERATIONS,
            HINT_SCHEMAS=HINT_SCHEMAS,
            HINT_PATHS=HINT_PATHS,
            OAS_SCHEMAS=schemas_list,          # raw data added
            OAS_OPERATIONS=operations_list,    # raw data added
        ),
        "structure": fmt_prompt(
            OAS_STRUCTURE_PROMPT,
            INFO_TITLE=INFO_TITLE,
            HINT_PATHS=HINT_PATHS,
            HINT_SCHEMAS=HINT_SCHEMAS,
            OAS_PATHS=paths_list,              # raw data added
        ),
        "examples": fmt_prompt(
            OAS_EXAMPLES_PROMPT,
            HINT_SCHEMAS=HINT_SCHEMAS,
            HINT_PARAMETERS=HINT_PARAMETERS,
            OAS_SCHEMAS=schemas_list,          # raw data added
            OAS_PARAMETERS=parameters_list,    # raw data added
        ),
    }

    # ── Step 5: Call agent — your existing loop, unchanged ────────────────────
    # Only change: parse result as SectionValidationResult instead of HTML rows

    report = ValidationReport(
        spec_title=spec.get("info", {}).get("title", "Unknown"),
        spec_version=str(spec.get("info", {}).get("version", "Unknown")),
    )

    for group_name, prompt in prompts.items():
        result: SectionValidationResult = agent.run(prompt)
        report.add_section(result)

    # ── Step 6: Render to HTML ────────────────────────────────────────────────
    return render_report(report)


# ── What your .md prompt files look like after the output section change ──────
#
# BEFORE (your current output instruction):
#
#   Output:
#   * A single HTML table row with columns: Non-compliant, Suggested Fix
#   * If zero violations, output nothing
#   * Format: [PARAMETERS][<rule_id>] <pointer> - <message>
#
# AFTER (structured JSON output — same for all .md files):
#
#   REQUIRED OUTPUT FORMAT:
#   Return only a single JSON object. No markdown. No text outside the JSON.
#
#   {
#     "section": "parameters",
#     "summary": "string",
#     "findings": [
#       {
#         "rule_id":       "STRING_CONSTRAINT_MISSING",
#         "section":       "parameters",
#         "severity":      "error",
#         "pointer":       "paths./users/{userId}.get.parameters[0]",
#         "message":       "what is wrong",
#         "suggested_fix": "how to fix it"
#       }
#     ]
#   }
#
#   If there are no violations return findings as an empty array [].
#
# The "section" value should match your canonical tag name for that file:
#   validate.correlation.md  → "section": "parameters"
#   validate.parameters.md   → "section": "parameters"
#   validate.reqresp.md      → "section": "request_response"
#   validate.structure.md    → "section": "api_structure"
#   validate.examples.md     → "section": "examples"
