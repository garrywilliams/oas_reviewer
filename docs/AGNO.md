# Agno Integration

## The Short Answer

`llm_caller.py` in the toolkit calls Azure OpenAI **directly** using the `openai`
Python SDK. It does not use Agno.

To use Agno instead, replace the `call_llm_for_section()` call with an Agno agent
configured with `response_model=SectionValidationResult`. Everything else in the
pipeline stays the same.

---

## Where agent.run() Fits

The call happens after prompt building and before assembling the ValidationReport:

```python
from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from oas_hints.validation_models import SectionValidationResult
from oas_hints.prompt_builder import build_section_prompt

# Create the agent once, reuse across all section calls
agent = Agent(
    model=AzureOpenAI(
        id="gpt-4.1",                        # your Azure deployment name
        azure_endpoint="https://YOUR_ENDPOINT.openai.azure.com/",
        azure_deployment="gpt-4.1",
        api_version="2024-02-01",
    ),
    response_model=SectionValidationResult,  # Agno handles JSON parsing
)

# Then for each section:
prompt = build_section_prompt(
    payload=hints["parameters"],
    validation_focus=YOUR_RULES["parameters"]["focus"],
    canonical_rule_ids=YOUR_RULES["parameters"]["rule_ids"],
)

result: SectionValidationResult = agent.run(prompt)
```

---

## Running Sections in Parallel

Each section prompt is independent, so all five can be fired concurrently:

```python
import asyncio
from agno.agent import Agent
from oas_hints.validation_models import SectionValidationResult, ValidationReport
from oas_hints.prompt_builder import build_section_prompt
from oas_hints import extract_all_hints
from oas_hints.loader import load_oas_string

async def validate_section(agent, section_name, payload, rules):
    prompt = build_section_prompt(
        payload=payload,
        validation_focus=rules["focus"],
        canonical_rule_ids=rules["rule_ids"],
    )
    result = await agent.arun(prompt)   # Agno async run
    return section_name, result

async def validate_spec(oas_string: str, section_rules: dict) -> ValidationReport:
    spec, errors = load_oas_string(oas_string)
    if spec is None:
        raise ValueError(f"Could not load spec: {errors}")

    all_hints = extract_all_hints(spec)

    agent = Agent(
        model=AzureOpenAI(
            id="gpt-4.1",
            azure_endpoint="https://YOUR_ENDPOINT.openai.azure.com/",
            azure_deployment="gpt-4.1",
            api_version="2024-02-01",
        ),
        response_model=SectionValidationResult,
    )

    # Fire all section prompts concurrently
    tasks = [
        validate_section(agent, name, payload, section_rules[name])
        for name, payload in all_hints.items()
        if name in section_rules
    ]
    section_results = await asyncio.gather(*tasks)

    # Assemble report
    report = ValidationReport(
        spec_title=spec.get("info", {}).get("title", "Unknown"),
        spec_version=str(spec.get("info", {}).get("version", "Unknown")),
    )
    for section_name, result in section_results:
        report.add_section(result)

    return report
```

---

## Repeatability Settings

Agno passes these through to the underlying model. Set them when creating the agent
or per-call depending on your Agno version:

```python
agent = Agent(
    model=AzureOpenAI(
        id="gpt-4.1",
        ...
    ),
    response_model=SectionValidationResult,
    # These are the key repeatability settings:
    temperature=0,      # Deterministic token selection
    seed=42,            # Same output family for same input (best-effort on Azure)
)
```

---

## What llm_caller.py Is For

`llm_caller.py` is included in the toolkit as a **reference implementation** showing
the raw Azure OpenAI call, the `system_fingerprint` logging (useful for detecting
model version drift), and the partial recovery path if Pydantic validation fails.

If you are using Agno, you can ignore `llm_caller.py` entirely — Agno handles JSON
parsing and model validation internally when `response_model` is set.
