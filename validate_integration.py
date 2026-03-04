"""
validate_integration.py  (updated for fact-table pipeline)
===========================================================
Shows how to integrate the fact-table approach into your existing validate.py.

Pipeline:
  load_oas_string_both()
      → resolved spec  → extract_all_hints()  → HINT_* strings
      → raw spec       → build_facts()         → fact rows
      → per rule group → filter_facts()        → filtered rows for that prompt
      → fmt_prompt()   → agent.run()           → SectionValidationResult
      → collate_results() → render_report()    → HTML
"""

import json
from oas_hints.loader import load_oas_string_both
from oas_hints import extract_all_hints
from oas_hints.fact_builder import build_facts, filter_facts
from oas_hints.validation_models import SectionValidationResult, ValidationReport
from oas_hints.html_renderer import render_report
from oas_hints.collate import collate_results


def validate_endpoint(spec_content: str, fmt_prompt, prompts_config: dict, agent) -> str:

    # ── Step 1: Load ──────────────────────────────────────────────────────────
    resolved, raw, errors = load_oas_string_both(spec_content)
    if resolved is None:
        raise ValueError(f"Could not load spec: {errors}")

    # ── Step 2: Deterministic hints (unchanged) ───────────────────────────────
    all_hints = extract_all_hints(resolved)

    HINT_PARAMETERS = all_hints["parameters"].hints_block()
    HINT_SCHEMAS    = all_hints["schemas"].hints_block()
    HINT_OPERATIONS = all_hints["operations"].hints_block()
    HINT_PATHS      = all_hints["paths"].hints_block()
    INFO_TITLE      = resolved.get("info", {}).get("title", "")

    # ── Step 3: Build fact table ──────────────────────────────────────────────
    all_facts = build_facts(resolved)["facts"]

    # correlation — only header parameters named correlationId
    FACTS_CORRELATION = json.dumps(
        [f for f in all_facts
         if f.get("kind") == "parameter"
         and f.get("in") == "header"
         and (f.get("name") or "").lower() == "correlationid"],
        indent=2
    )

    # parameters — all parameter facts
    FACTS_PARAMETERS = json.dumps(
        filter_facts(all_facts, ["parameter"]),
        indent=2
    )

    # examples — schema properties and example_value facts
    FACTS_EXAMPLES = json.dumps(
        filter_facts(all_facts, ["schema_property", "example_value"]),
        indent=2
    )

    # reqresp — schema property facts
    FACTS_REQRESP = json.dumps(
        filter_facts(all_facts, ["schema_property"]),
        indent=2
    )

    # structure — operation facts + path/query parameter facts
    FACTS_STRUCTURE = json.dumps(
        filter_facts(all_facts, ["operation"]) +
        [f for f in all_facts
         if f.get("kind") == "parameter"
         and f.get("in") in ("path", "query")],
        indent=2
    )

    # ── Step 4: Build prompts ─────────────────────────────────────────────────
    prompts = {
        "correlation": fmt_prompt(
            prompts_config["OAS_CORRELATION_PROMPT"],
            HINT_PARAMETERS=HINT_PARAMETERS,
            FACTS=FACTS_CORRELATION,
        ),
        "parameters": fmt_prompt(
            prompts_config["OAS_PARAMETERS_PROMPT"],
            HINT_PARAMETERS=HINT_PARAMETERS,
            FACTS=FACTS_PARAMETERS,
        ),
        "examples": fmt_prompt(
            prompts_config["OAS_EXAMPLES_PROMPT"],
            HINT_PARAMETERS=HINT_PARAMETERS,
            HINT_SCHEMAS=HINT_SCHEMAS,
            FACTS=FACTS_EXAMPLES,
        ),
        "reqresp": fmt_prompt(
            prompts_config["OAS_REQRESP_PROMPT"],
            HINT_OPERATIONS=HINT_OPERATIONS,
            HINT_SCHEMAS=HINT_SCHEMAS,
            FACTS=FACTS_REQRESP,
        ),
        "structure": fmt_prompt(
            prompts_config["OAS_STRUCTURE_PROMPT"],
            HINT_PATHS=HINT_PATHS,
            HINT_OPERATIONS=HINT_OPERATIONS,
            INFO_TITLE=INFO_TITLE,
            FACTS=FACTS_STRUCTURE,
        ),
    }

    # ── Step 5: Your existing parallel agent calls ────────────────────────────
    # ... ThreadPoolExecutor + as_completed loop unchanged ...
    # results[key] = agent.run(prompt).content

    # ── Step 6: Collate and render ────────────────────────────────────────────
    keys = ("correlation", "parameters", "examples", "reqresp", "structure")
    # html = collate_results(resolved, keys, results)
    # return ChatMessage(role="assistant", content=html)
