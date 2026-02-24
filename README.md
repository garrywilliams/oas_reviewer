# OAS Validation Toolkit — Hint Extractors

Pre-processing utilities that convert a resolved OAS 3.x specification into
structured, section-scoped **hints** for use in LLM prompt construction.

## Purpose

Rather than sending raw OAS JSON to an LLM and hoping it finds everything,
this toolkit pre-digests the spec into structured observations per section.
Each hint has a severity (`error` / `warning` / `info`), a dot-notation
`location`, and a human-readable `message`. These hints are embedded into
LLM prompts alongside the raw section data, focusing the model's attention
and dramatically improving repeatability.

## Architecture

```
Raw OAS YAML/JSON string
        ↓
   loader.py  (NoDatesSafeLoader + jsonref $ref resolution)
        ↓
   extract_all_hints(spec)
        ↓
   ┌──────────┬──────────┬────────────┬─────────┬────────────┐
   │   info   │  paths   │ operations │ schemas │ parameters │
   └──────────┴──────────┴────────────┴─────────┴────────────┘
        ↓ (SectionPayload per section)
   hints_block()  →  embed in prompt  →  fire to Azure GPT-4.1
```

## Installation

```bash
pip install jsonref pyyaml prance openai
```

## Quick Start

```python
from oas_hints.loader import load_oas_string
from oas_hints import extract_all_hints

spec, errors = load_oas_string(your_yaml_string)

all_hints = extract_all_hints(spec)

for section_name, payload in all_hints.items():
    print(payload.hints_block())
    # Use payload.raw_data + payload.hints_block() to build your LLM prompt
```

## Hint extractors

| Module | Covers |
|---|---|
| `info_hints.py` | title, version, description, contact, license, terms of service |
| `paths_hints.py` | path format, naming, trailing slashes, path param consistency, duplicates |
| `operations_hints.py` | operationId, summary, tags, responses, request bodies, security |
| `schemas_hints.py` | naming convention, types, property descriptions, required/missing fields, enums |
| `parameters_hints.py` | in/required rules, forbidden headers, schema completeness, naming |

## Extending

Add a new rule by appending a `Hint(...)` inside the relevant extractor function.
Add a new section by creating a new `*_hints.py` following the existing pattern,
then registering it in `__init__.py:extract_all_hints()`.

## Key design decisions

- **Date-safe loader**: Invalid example dates (e.g. 31 April) do not cause parse failures
- **$ref resolution first**: All hints operate on fully materialised data — no `$ref` stubs
- **Hints are deterministic**: Same input always produces same hints, making them safe
  to use in repeatability-sensitive LLM workflows
- **SectionPayload.raw_data**: The raw OAS fragments are kept alongside hints so you
  can include them in prompts without re-extracting

## Running the demo

```bash
python demo.py
```
