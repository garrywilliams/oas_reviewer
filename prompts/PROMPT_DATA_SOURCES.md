# Prompt Data Sources

Summary of which hints and raw OAS data each prompt requires.

| Prompt | Hints | OAS Data |
|---|---|---|
| validate.correlation | HINT_PARAMETERS | OAS_PARAMETERS |
| validate.parameters | HINT_PARAMETERS | OAS_PARAMETERS |
| validate.examples | HINT_PARAMETERS, HINT_SCHEMAS | OAS_PARAMETERS, OAS_SCHEMAS |
| validate.reqresp | HINT_OPERATIONS, HINT_SCHEMAS | OAS_OPERATIONS, OAS_SCHEMAS |
| validate.structure | HINT_PATHS, HINT_OPERATIONS | OAS_PATHS, OAS_OPERATIONS, INFO_TITLE |

## Why each choice was made

**correlation** — correlationId is a header parameter. Parameters extractor
already walks all locations (components, path-level, operation-level) so
nothing is missed.

**parameters** — all parameter concerns live in the parameters section.
Schemas and operations are not needed — the extractor already captures
inline parameter schemas.

**examples** — examples appear in both parameter definitions and schema
properties, so both are needed.

**reqresp** — request bodies and response schemas are defined in operations
(the requestBody/responses objects) and in component schemas. Paths are not
needed — the operations extractor already captures path and method context.

**structure** — title lives in info (passed as raw string not hint block),
path parameter filtering needs path structure, action-switching query params
and unrelated operations need operation context.

## fmt_prompt() calls

```python
prompts = {
    "correlation": fmt_prompt(
        OAS_CORRELATION_PROMPT,
        HINT_PARAMETERS=HINT_PARAMETERS,
        OAS_PARAMETERS=OAS_PARAMETERS,
    ),
    "parameters": fmt_prompt(
        OAS_PARAMETERS_PROMPT,
        HINT_PARAMETERS=HINT_PARAMETERS,
        OAS_PARAMETERS=OAS_PARAMETERS,
    ),
    "examples": fmt_prompt(
        OAS_EXAMPLES_PROMPT,
        HINT_PARAMETERS=HINT_PARAMETERS,
        HINT_SCHEMAS=HINT_SCHEMAS,
        OAS_PARAMETERS=OAS_PARAMETERS,
        OAS_SCHEMAS=OAS_SCHEMAS,
    ),
    "reqresp": fmt_prompt(
        OAS_REQRESP_PROMPT,
        HINT_OPERATIONS=HINT_OPERATIONS,
        HINT_SCHEMAS=HINT_SCHEMAS,
        OAS_OPERATIONS=OAS_OPERATIONS,
        OAS_SCHEMAS=OAS_SCHEMAS,
    ),
    "structure": fmt_prompt(
        OAS_STRUCTURE_PROMPT,
        HINT_PATHS=HINT_PATHS,
        HINT_OPERATIONS=HINT_OPERATIONS,
        INFO_TITLE=INFO_TITLE,
        OAS_PATHS=OAS_PATHS,
        OAS_OPERATIONS=OAS_OPERATIONS,
    ),
}
```
