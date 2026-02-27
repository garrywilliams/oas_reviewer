# Prompt Format Reference

Each section prompt is built by `prompt_builder.py` using `build_section_prompt()`.
The prompt has six blocks in a fixed order.

---

## The Six Blocks

### 1. Role instruction
Sets the model's behaviour for the entire prompt.
```
You are a strict API quality reviewer validating an OpenAPI Specification 3.x document.
Your job is to check the PARAMETERS section against the rules below and return a
structured JSON response.
```

### 2. Pre-flight observations
Deterministic hints from the extractors. These are facts, not opinions — the model
should treat them as reliable and not re-derive them. Its job is to find what the
hints may have missed.
```
PRE-FLIGHT OBSERVATIONS (deterministic checks already performed)
[ERROR]   paths./users/{userId}/orders.get.parameters[0] — path parameter
          'userId' must have required: true
[INFO]    paths./users/{userId}/orders.get.parameters[1] — query parameter
          'status' is an unconstrained string
```

### 3. Raw section data
The resolved JSON for this section only. No `$ref` stubs — all references have been
materialised by the loader before the prompt is built.
```
PARAMETERS DATA:
{ ...json... }
```

### 4. Validation focus
Your rule bullets. These are unchanged from your existing prompts.
```
VALIDATION FOCUS:
* Path parameters must declare required: true
* All parameters must have a description
* Query string parameters should have constraints (maxLength, enum, or format)
```

### 5. Canonical rule IDs
The only `rule_id` values the model is permitted to use. If a violation does not
match exactly, the model maps to the closest one. It must not invent new IDs.
```
CANONICAL RULE IDs (use only these, no others):
PATH_PARAM_NOT_REQUIRED, DESCRIPTION_MISSING, STRING_UNCONSTRAINED,
NAMING_CONVENTION, FORBIDDEN_HEADER, ARRAY_ITEMS_MISSING
```

### 6. Required output format
The full Pydantic-generated JSON schema injected literally, followed by a concrete
example of one correctly formed finding. The model is told to return only JSON with
no markdown fences and no text outside the object.
```
REQUIRED OUTPUT FORMAT:
Return ONLY a single valid JSON object matching this schema exactly.
No markdown fences. No explanation outside the JSON. No trailing text.

{ ...json schema... }

Example of a single finding object:
{ ...example finding... }
```

---

## Before and After

### Before (HTML output)
```
Validation Focus:
* Path parameters must declare required: true
* All parameters must have a description

Canonical rule IDs:
[PARAMETERS]: PATH_PARAM_NOT_REQUIRED, DESCRIPTION_MISSING

Output:
* A single HTML table row with columns: Non-compliant, Suggested Fix
* If zero violations, output nothing
* Format: [PARAMETERS][<rule_id>] <pointer> - <message>
```

### After (structured JSON output)
```
You are a strict API quality reviewer checking the PARAMETERS section
of an OpenAPI 3.x document.

PRE-FLIGHT OBSERVATIONS:
[ERROR] paths./users/{userId}/orders.get.parameters[0] — path parameter
  'userId' must have required: true

PARAMETERS DATA:
<resolved JSON>

VALIDATION FOCUS:
* Path parameters must declare required: true
* All parameters must have a description

CANONICAL RULE IDs (use only these, no others):
PATH_PARAM_NOT_REQUIRED, DESCRIPTION_MISSING

REQUIRED OUTPUT FORMAT:
Return only a single JSON object. No markdown. No text outside the JSON.

{
  "section": "parameters",
  "summary": "string",
  "findings": [
    {
      "rule_id": "PATH_PARAM_NOT_REQUIRED",
      "section": "parameters",
      "severity": "error",
      "pointer": "paths./users/{userId}/orders.get.parameters[0]",
      "message": "Path parameter 'userId' must declare required: true",
      "suggested_fix": "Add required: true to the userId parameter"
    }
  ]
}

If there are no violations return findings as an empty array [].
```

---

## What Changed

| | Before | After |
|---|---|---|
| Output instruction | HTML table row format | JSON schema (from Pydantic) |
| Pre-flight hints | Not present | Injected at top |
| Raw data | Full spec or large chunk | Section slice only, fully resolved |
| Rule bullets | Same | Same — unchanged |
| Canonical IDs | Same | Same — unchanged |
| Zero violations | "output nothing" | `"findings": []` |
