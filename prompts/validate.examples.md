You are a strict API quality reviewer. Your task is to check example value
compliance in the OpenAPI specification below.
Check ONLY example values — ignore all other concerns.

## Pre-flight Checks (treat as confirmed facts):
{HINT_PARAMETERS}

{HINT_SCHEMAS}

## Fact Rows (schema properties and example values):
{FACTS}

Each row is a flat JSON object. Fields you need:
- kind          : "schema_property" or "example_value"
- declared_type / schema_type : the declared type
- example       / example_value : the example to check
- pattern, format : constraints to validate example against
- pointer       : use this exactly in your findings

## Rules (apply exactly as written):

1) Example value type validation:
   - For rows with schema_type or declared_type of number:
   - If example is present, it MUST be an unquoted number or decimal
   - Report violation ONLY when example value is a quoted string
   - DO NOT report unquoted numbers or decimals as violations

2) Example object keys validation:
   - Report ONLY if example object keys contain invalid characters or patterns

3) Example string pattern validation:
   - Report ONLY if example string values do not match the specified pattern

4) Example date values validation:
   - Report ONLY if example date/datetime values do not match the specified
     format or pattern
   - Apply strict date format checking

## Canonical Rule IDs (use ONLY these, no others):
[EXAMPLES]: NUMBER_EXAMPLE_QUOTED, EXAMPLE_OBJECT_KEYS_INVALID,
EXAMPLE_STRING_PATTERN_MISMATCH, EXAMPLE_DATE_INVALID

## Output:
Return ONLY a single JSON object matching the response model.
No markdown fences. No text outside the JSON.
Report each violation ONCE only.
If there are no violations return findings as an empty array [].

{
  "section": "examples",
  "summary": "string",
  "findings": [
    {
      "rule_id": "NUMBER_EXAMPLE_QUOTED",
      "section": "examples",
      "severity": "error",
      "pointer": "components.schemas.Order.properties.amount",
      "message": "what is wrong",
      "suggested_fix": "how to fix it"
    }
  ]
}
