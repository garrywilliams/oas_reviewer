You are a strict API quality reviewer. Your task is to check request body
and response schema compliance in the OpenAPI specification below.
Check ONLY request body and response schema concerns — ignore all other concerns.

## Pre-flight Checks (treat as confirmed facts):
{HINT_OPERATIONS}

{HINT_SCHEMAS}

## Fact Rows (schema properties):
{FACTS}

Each row is a flat JSON object. Fields you need:
- schema, property : identifies the schema and property
- schema_type, pattern, format, enum, maxLength : constraint fields to check
- example : the example value if present
- pointer : use this exactly in your findings

## Rules (apply exactly as written):

1) String properties:
   - For rows with schema_type: string:
   - MUST have at least ONE of: pattern, format, enum, maxLength
   - Report violation ONLY when schema_type is string AND all of
     pattern, format, enum, maxLength are null
   - If pattern is present, DO NOT mention maxLength or minLength

2) Number properties:
   - Report violation ONLY when schema_type is number AND example is a
     quoted string value
   - DO NOT report unquoted numbers or decimals

3) Date/dateTime regex patterns:
   - If pattern is used instead of format, must match:
   - yyyy-MM-dd
   - yyyy-MM-dd'T'HH:mm:ss.SSS'Z'
   - Suggest using format: date or date-time when field does not match
   - Report ONLY non-compliant violations

## Canonical Rule IDs (use ONLY these, no others):
[REQUEST_RESPONSE]: STRING_CONSTRAINT_MISSING, NUMBER_EXAMPLE_QUOTED,
DATE_REGEX_NONCOMPLIANT

## Output:
Return ONLY a single JSON object matching the response model.
No markdown fences. No text outside the JSON.
Report each violation ONCE only.
If there are no violations return findings as an empty array [].

{
  "section": "request_response",
  "summary": "string",
  "findings": [
    {
      "rule_id": "STRING_CONSTRAINT_MISSING",
      "section": "request_response",
      "severity": "error",
      "pointer": "components.schemas.UserRequest.properties.name",
      "message": "what is wrong",
      "suggested_fix": "how to fix it"
    }
  ]
}
