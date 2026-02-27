"""
llm_caller.py
=============
Sends section prompts to Azure OpenAI (GPT-4.1) and parses structured responses.

Key settings for repeatability:
  - temperature=0       : deterministic token selection
  - seed=FIXED_SEED     : same sequence for same input (best-effort on Azure)
  - response_format=json: prevents markdown wrapping
  - Pydantic validation  : catches malformed responses before they reach your pipeline
"""
from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from .validation_models import SectionValidationResult

logger = logging.getLogger(__name__)

# Fixed seed for reproducibility — change only if you want a different but
# equally stable output family
FIXED_SEED = 42


def call_llm_for_section(
    client,               # openai.AzureOpenAI instance
    deployment_name: str, # Your Azure deployment name e.g. "gpt-4.1"
    prompt: str,
    system_prompt: str | None = None,
    max_tokens: int = 2048,
    seed: int = FIXED_SEED,
) -> tuple[SectionValidationResult | None, list[str]]:
    """
    Send a section prompt to Azure OpenAI and parse the structured response.

    Args:
        client:          AzureOpenAI client instance.
        deployment_name: Azure deployment name for your GPT-4.1 model.
        prompt:          The full section prompt from build_section_prompt().
        system_prompt:   Optional system message override.
        max_tokens:      Max tokens for the response.
        seed:            Seed for reproducibility.

    Returns:
        Tuple of (SectionValidationResult | None, list[str] errors).
        Result is None only if parsing failed entirely.
    """
    errors: list[str] = []

    system = system_prompt or (
        "You are a strict API quality reviewer. "
        "You always respond with valid JSON matching the schema provided. "
        "You never add explanation or markdown outside the JSON object."
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": prompt},
    ]

    # ── Call the model ─────────────────────────────────────────────────────────
    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=messages,
            temperature=0,
            seed=seed,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},  # Prevents markdown wrapping
        )
    except Exception as e:
        errors.append(f"Azure OpenAI call failed: {e}")
        logger.error("LLM call failed", exc_info=True)
        return None, errors

    # ── Extract content ────────────────────────────────────────────────────────
    raw_content = response.choices[0].message.content or ""

    # Log system_fingerprint so you can detect model version drift
    fingerprint = getattr(response, "system_fingerprint", None)
    if fingerprint:
        logger.debug("system_fingerprint: %s", fingerprint)

    # ── Parse JSON ─────────────────────────────────────────────────────────────
    try:
        raw_dict = json.loads(raw_content)
    except json.JSONDecodeError as e:
        errors.append(f"LLM returned invalid JSON: {e}")
        logger.error("JSON parse failed. Raw content:\n%s", raw_content[:500])
        return None, errors

    # ── Validate against Pydantic model ───────────────────────────────────────
    try:
        result = SectionValidationResult.model_validate(raw_dict)
    except ValidationError as e:
        errors.append(f"LLM response failed schema validation: {e}")
        logger.error("Pydantic validation failed. Raw dict: %s", raw_dict)

        # Attempt a graceful partial recovery — extract any findings we can
        result = _partial_recovery(raw_dict, errors)

    return result, errors


def _partial_recovery(raw_dict: dict[str, Any], errors: list[str]) -> SectionValidationResult | None:
    """
    If full validation fails, try to salvage a partial result.
    This handles cases where the LLM returned mostly-correct JSON
    with one or two malformed finding objects.
    """
    section = raw_dict.get("section", "unknown")
    summary = raw_dict.get("summary", "")
    findings = []

    for i, raw_finding in enumerate(raw_dict.get("findings", [])):
        try:
            from .validation_models import Finding
            findings.append(Finding.model_validate(raw_finding))
        except ValidationError as e:
            errors.append(f"Finding[{i}] could not be parsed and was dropped: {e}")
            logger.warning("Dropped finding[%d]: %s", i, raw_finding)

    if findings or section != "unknown":
        logger.warning("Partial recovery succeeded: %d findings rescued", len(findings))
        return SectionValidationResult(section=section, findings=findings, summary=summary)

    return None
