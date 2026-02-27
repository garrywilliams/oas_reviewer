# Pydantic Models Reference

All models are in `oas_hints/validation_models.py`.

---

## Severity

```python
class Severity(str, Enum):
    ERROR   = "error"    # Clear, unambiguous violation
    WARNING = "warning"  # Likely issue; context may be needed
    INFO    = "info"     # Advisory; not a hard violation
```

---

## Finding

One rule violation. This is the atomic unit of the report.

```python
class Finding(BaseModel):
    rule_id:       str       # SCREAMING_SNAKE_CASE, must be from canonical list
    section:       str       # info | paths | operations | schemas | parameters
    severity:      Severity  # error | warning | info
    pointer:       str       # dot-notation location in the spec
    message:       str       # what is wrong — specific, no repeating rule_id/pointer
    suggested_fix: str       # concrete and actionable, include example values
```

**pointer examples:**
```
info.title
paths./users/{userId}.get
paths./users/{userId}.get.parameters[0]
components.schemas.User.properties.tags
components.schemas.order_response
```

**Helper methods:**
```python
finding.label()            # → "[PARAMETERS][PATH_PARAM_NOT_REQUIRED]"
finding.full_description() # → "[PARAMETERS][PATH_PARAM_NOT_REQUIRED] paths... - message"
```

---

## SectionValidationResult

What the LLM returns for one section prompt.
This is the Agno `response_model`.

```python
class SectionValidationResult(BaseModel):
    section:  str            # must match the section the prompt was built for
    findings: list[Finding]  # empty list [] if clean — never omit this field
    summary:  str            # 1-2 sentences plain English quality summary
```

**Properties (computed, not returned by LLM):**
```python
result.has_findings    # bool
result.error_count     # int
result.warning_count   # int
result.info_count      # int
```

---

## ValidationReport

Assembled in Python from all section results. Never returned by the LLM.

```python
class ValidationReport(BaseModel):
    spec_title:   str
    spec_version: str
    sections:     dict[str, SectionValidationResult]
```

**Usage:**
```python
report = ValidationReport(
    spec_title=spec["info"]["title"],
    spec_version=spec["info"]["version"],
)

for section_name, result in section_results:
    report.add_section(result)
```

**Properties:**
```python
report.all_findings    # list[Finding] across all sections
report.total_errors    # int
report.total_warnings  # int
report.total_info      # int
```

---

## How the Models Connect to the Prompt

`build_section_prompt()` calls `SectionValidationResult.model_json_schema()` and
injects the result directly into the prompt. This means:

- The prompt and the parser are always in sync
- Adding a field to `Finding` automatically updates the prompt contract
- The LLM has an unambiguous structural specification to follow

```python
# This is what gets injected into every prompt:
schema = SectionValidationResult.model_json_schema()
# → full JSON Schema object describing the expected response structure
```
