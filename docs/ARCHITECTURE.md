# OAS Validation Toolkit — Architecture

## Overview

The toolkit validates an OpenAPI Specification document against a set of quality
rules by combining deterministic pre-processing with LLM-based judgement checks.
Results are returned as structured JSON, then rendered to HTML.

---

## Pipeline

```
Raw OAS YAML/JSON string
        │
        ▼
┌───────────────┐
│   loader.py   │  • Date-safe YAML parse (handles invalid dates e.g. 31 April)
│               │  • $ref resolution (all references materialised inline)
└───────┬───────┘
        │  resolved spec dict
        ▼
┌───────────────┐
│ extract_all_  │  • Five deterministic extractors run in sequence
│   hints()     │  • Each produces a SectionPayload (hints + raw data)
└───────┬───────┘
        │  dict[section → SectionPayload]
        ▼
┌───────────────┐
│ prompt_builder│  • Builds one prompt per section
│               │  • Injects: hints, raw JSON, your rules, canonical rule IDs,
│               │    Pydantic JSON schema, concrete example
└───────┬───────┘
        │  4–5 prompt strings
        ▼
┌───────────────┐
│  Agno Agent   │  • response_model=SectionValidationResult
│  agent.run()  │  • temperature=0, seed=42, response_format=json_object
│               │  • One agent.run() call per section (run in parallel)
└───────┬───────┘
        │  SectionValidationResult per section
        ▼
┌───────────────┐
│ ValidationRe- │  • Assembled in Python from all section results
│    port       │  • Never returned by the LLM
└───────┬───────┘
        │
        ▼
┌───────────────┐
│ html_renderer │  • render_report(report) → self-contained HTML string
└───────────────┘
```

---

## File Structure

```
oas_hints/
├── __init__.py            Exports all public symbols
├── loader.py              YAML/JSON string → resolved spec dict
├── models.py              Hint, Severity, SectionPayload (pre-processing types)
├── info_hints.py          Deterministic hints: info section
├── paths_hints.py         Deterministic hints: paths section
├── operations_hints.py    Deterministic hints: operations
├── schemas_hints.py       Deterministic hints: component schemas
├── parameters_hints.py    Deterministic hints: parameters
├── validation_models.py   Pydantic: Finding, SectionValidationResult, ValidationReport
├── prompt_builder.py      Assembles the structured prompt for each section
├── llm_caller.py          Direct Azure OpenAI call (no Agno) — see AGNO.md
└── html_renderer.py       ValidationReport → HTML
```

---

## Key Design Decisions

**Deterministic hints first** — The extractors catch everything that can be caught
with certainty (missing fields, type errors, naming violations). These are injected
into the prompt so the LLM does not waste reasoning on things that are structurally
obvious. It focuses only on things that require judgement.

**Section chunking** — The spec is split into 4–5 logical groups before being sent
to the LLM. This gives more consistent, repeatable results than one large prompt
containing the full spec, because each prompt has a focused, bounded scope.

**Structured output** — The LLM returns `SectionValidationResult` JSON rather than
HTML fragments. This separates data from presentation, makes findings sortable and
filterable, and allows the HTML renderer to be changed independently of the prompts.

**Canonical rule IDs** — Each section prompt includes an explicit list of valid rule
IDs. The LLM is instructed to use only these. Combined with `temperature=0` and a
fixed `seed`, this makes `rule_id` values stable across runs — developers can track
which rules are failing as they fix issues.

**Repeatability** — Same spec in → same findings out. This is the core requirement.
It is achieved by: deterministic pre-processing, fixed temperature and seed, JSON
response format (prevents markdown variation), and Pydantic validation on the response.
