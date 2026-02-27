"""
prompt_builder.py
=================
Builds structured prompts for each OAS section.

Key idea: the JSON schema of SectionValidationResult is injected directly
into each prompt so the LLM knows the exact structure to return.
This, combined with temperature=0 and seed=, gives highly consistent output.
"""
from __future__ import annotations

import json
from .validation_models import SectionValidationResult, Finding
from .models import SectionPayload


def _json_schema_block() -> str:
    """
    Render the SectionValidationResult JSON schema as a prompt-friendly string.
    Injected once per prompt so the LLM has an unambiguous contract.
    """
    schema = SectionValidationResult.model_json_schema()
    return json.dumps(schema, indent=2)


def _finding_example(section: str, rule_id: str, pointer: str) -> str:
    """Render a concrete Finding example for the prompt."""
    example = Finding(
        rule_id=rule_id,
        section=section,
        severity="error",
        pointer=pointer,
        message="Example of what goes in message — specific, no repetition of rule_id or pointer.",
        suggested_fix="Example of a concrete fix suggestion."
    )
    return json.dumps(example.model_dump(), indent=2)


def build_section_prompt(
    payload: SectionPayload,
    validation_focus: list[str],
    canonical_rule_ids: list[str],
    extra_context: str = "",
) -> str:
    """
    Build the full prompt for a single OAS section.

    Args:
        payload:            SectionPayload from the hint extractor.
        validation_focus:   Bullet-point rules to check (your existing rule bullets).
        canonical_rule_ids: List of SCREAMING_SNAKE_CASE rule IDs valid for this section.
        extra_context:      Any additional instructions specific to this section.

    Returns:
        Complete prompt string ready to send to the LLM.
    """
    section = payload.section.upper()
    hints_block = payload.hints_block()
    raw_json = json.dumps(payload.raw_data, indent=2)
    schema_block = _json_schema_block()
    rules_block = "\n".join(f"* {r}" for r in validation_focus)
    rule_ids_block = ", ".join(canonical_rule_ids)

    # Build a concrete example using the first rule ID so the model
    # has something real to pattern-match against
    example_rule = canonical_rule_ids[0] if canonical_rule_ids else "EXAMPLE_RULE"
    example_pointer = f"components.schemas.Example.properties.field_name"
    finding_example = _finding_example(payload.section, example_rule, example_pointer)

    prompt = f"""You are a strict API quality reviewer validating an OpenAPI Specification 3.x document.
Your job is to check the {section} section against the rules below and return a structured JSON response.

══════════════════════════════════════════════════════════════════
PRE-FLIGHT OBSERVATIONS (deterministic checks already performed)
══════════════════════════════════════════════════════════════════
The following observations were produced deterministically before you were invoked.
Use these as strong signals — they are reliable and do not need re-verification.
Focus your analysis on issues the observations may have missed.

{hints_block}

══════════════════════════════════════════════════════════════════
{section} DATA
══════════════════════════════════════════════════════════════════
{raw_json}

══════════════════════════════════════════════════════════════════
VALIDATION FOCUS
══════════════════════════════════════════════════════════════════
{rules_block}
{("\\n" + extra_context) if extra_context else ""}
══════════════════════════════════════════════════════════════════
CANONICAL RULE IDs FOR THIS SECTION
══════════════════════════════════════════════════════════════════
You MUST use only these rule_id values in your findings:
{rule_ids_block}

If a violation does not match any of these rule IDs, map it to the closest one.
Do not invent new rule IDs.

══════════════════════════════════════════════════════════════════
REQUIRED OUTPUT FORMAT
══════════════════════════════════════════════════════════════════
Return ONLY a single valid JSON object matching this schema exactly.
No markdown fences. No explanation outside the JSON. No trailing text.

{schema_block}

Example of a single finding object:
{finding_example}

Rules for findings:
- pointer must use dot-notation (e.g. paths./users/{{userId}}.get.parameters[0])
- message must be specific — describe the exact issue, not a generic observation
- suggested_fix must be actionable — include example values where relevant
- If there are zero violations, return an empty findings array — do not omit the field
- section must be exactly: {payload.section}
- severity must be exactly one of: error, warning, info
"""
    return prompt
