# Integration Guide

## What Changes in Your Codebase

Only three things change. Everything else — your rule files, your `prompts` dict,
your `fmt_prompt()` function, your `agent.run()` loop — stays exactly as it is.

---

## Change 1 — Hint Variables

Replace your existing pre-processing step with the toolkit extractors.
Your variable names stay the same; they just come from a different source.

```python
from oas_hints.loader import load_oas_string
from oas_hints import extract_all_hints
import json

spec, errors = load_oas_string(spec_content)
all_hints = extract_all_hints(spec)

# Drop-in replacements for your existing hint variables:
HINT_PARAMETERS = all_hints["parameters"].hints_block()
HINT_SCHEMAS    = all_hints["schemas"].hints_block()
HINT_OPERATIONS = all_hints["operations"].hints_block()
HINT_PATHS      = all_hints["paths"].hints_block()
INFO_TITLE      = spec.get("info", {}).get("title", "")

# Raw OAS fragments for LLM context:
parameters_list = json.dumps(all_hints["parameters"].raw_data, indent=2)
schemas_list    = json.dumps(all_hints["schemas"].raw_data,    indent=2)
operations_list = json.dumps(all_hints["operations"].raw_data, indent=2)
paths_list      = json.dumps(all_hints["paths"].raw_data,      indent=2)
```

---

## Change 2 — Your .md Prompt Files

Only the output instruction at the bottom of each file changes.
Your validation focus, rules, and canonical rule IDs are untouched.

### Before
```
Output:
* A single HTML table row with columns: Non-compliant, Suggested Fix
* If zero violations, output nothing
* Format: [PARAMETERS][<rule_id>] <pointer> - <message>
```

### After (same block for all .md files)
```
REQUIRED OUTPUT FORMAT:
Return only a single JSON object. No markdown. No text outside the JSON.

{
  "section": "parameters",
  "summary": "string",
  "findings": [
    {
      "rule_id":       "STRING_CONSTRAINT_MISSING",
      "section":       "parameters",
      "severity":      "error",
      "pointer":       "paths./users/{userId}.get.parameters[0]",
      "message":       "what is wrong",
      "suggested_fix": "how to fix it"
    }
  ]
}

If there are no violations return findings as an empty array [].
```

The `section` value per file:

| Your .md file | section value |
|---|---|
| validate.correlation.md | `parameters` |
| validate.parameters.md | `parameters` |
| validate.reqresp.md | `request_response` |
| validate.structure.md | `api_structure` |
| validate.examples.md | `examples` |

---

## Change 3 — Response Handling

Replace the HTML row string-join with Pydantic parsing and a single render call.

### Before
```python
html_rows = []
for group_name, prompt in prompts.items():
    response = agent.run(prompt)
    html_rows.append(response)  # raw HTML fragment

html = "<table>..." + "".join(html_rows) + "</table>"
```

### After
```python
from oas_hints.validation_models import SectionValidationResult, ValidationReport
from oas_hints.html_renderer import render_report

report = ValidationReport(
    spec_title=spec.get("info", {}).get("title", "Unknown"),
    spec_version=str(spec.get("info", {}).get("version", "Unknown")),
)

for group_name, prompt in prompts.items():
    result: SectionValidationResult = agent.run(prompt)
    report.add_section(result)

html = render_report(report)
```

---

## Your Rule Group to Data Source Mapping

Each rule group needs hints and raw data from specific sections:

| Rule group | Hints from | Raw data from |
|---|---|---|
| correlation | HINT_PARAMETERS | parameters_list |
| parameters | HINT_PARAMETERS, HINT_SCHEMAS, HINT_OPERATIONS | parameters_list |
| reqresp | HINT_OPERATIONS, HINT_SCHEMAS, HINT_PATHS | schemas_list, operations_list |
| structure | HINT_PATHS, HINT_SCHEMAS | paths_list |
| examples | HINT_SCHEMAS, HINT_PARAMETERS | schemas_list, parameters_list |

Pass the raw data into `fmt_prompt()` as additional template variables alongside
your existing hint variables. Your `.md` files reference them as `{OAS_PARAMETERS}`,
`{OAS_SCHEMAS}` etc. in the data block.

---

## Agno Agent Configuration

```python
from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from oas_hints.validation_models import SectionValidationResult

agent = Agent(
    model=AzureOpenAI(
        id="gpt-4.1",
        azure_endpoint="https://YOUR_ENDPOINT.openai.azure.com/",
        azure_deployment="gpt-4.1",
        api_version="2024-02-01",
    ),
    response_model=SectionValidationResult,
    temperature=0,
    seed=42,
)
```

Agno handles JSON parsing and Pydantic validation internally when
`response_model` is set. `llm_caller.py` in the toolkit is a reference
implementation only — you do not need it if you are using Agno.
