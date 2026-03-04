You are a strict API quality reviewer. Your task is to check parameter
compliance in the OpenAPI specification below.
Check ONLY parameter concerns — ignore all other concerns.

## Pre-flight Checks (treat as confirmed facts):
{HINT_PARAMETERS}

## Fact Rows (all parameters):
{FACTS}

Each row is a flat JSON object. Fields you need:
- name, in, required, schema_type, pattern, format, enum, maxLength
- pointer : use this exactly in your findings

## Rules (apply exactly as written):

1) String constraint validation:
   - For header, path, and query parameters with schema_type: string:
   - MUST have exactly ONE of: pattern, format, enum, maxLength
   - IGNORE example constraint entirely
   - If pattern is present, DO NOT report maxLength even if pattern encodes length
   - Report violation ONLY when schema_type is string AND all of
     pattern, format, enum, maxLength are null

2) Uppercase parameter names:
   - Report violation ONLY when path or query parameter name is defined
     entirely in UPPER CASE
   - EXCLUDE: path schema segment patterns and enum values

3) correlationId header:
   - Must have ONLY one of:
   - pattern matching regex: ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$
   - OR format: uuid
   - Report violation ONLY if pattern fails to match regex OR format is not uuid

4) correlationId name:
   - Report violation if different capitalisations of correlationId have been
     used such as CorrelationId and correlationID in different locations

5) Custom headers (x-*):
   - Must represent metadata only, NOT business data
   - Report violations if x- header contains business data

6) Date/dateTime regex patterns:
   - If pattern is used instead of format, must match:
   - yyyy-MM-dd
   - yyyy-MM-dd'T'HH:mm:ss.SSS'Z'
   - Suggest using format: date or date-time when field does not match
   - Report ONLY non-compliant violations

7) Query vs Path parameter ambiguity:
   - Report ONLY when ambiguity between query and path parameters is identified

## Canonical Rule IDs (use ONLY these, no others):
[PARAMETERS]: STRING_CONSTRAINT_MISSING, PARAM_UPPERCASE_NAME,
CORRELATION_ID_FORMAT, CORRELATION_ID_NAME, HEADER_BUSINESS_DATA,
DATE_REGEX_NONCOMPLIANT, PARAM_AMBIGUITY

## Output:
Return ONLY a single JSON object matching the response model.
No markdown fences. No text outside the JSON.
Report each violation ONCE only.
If there are no violations return findings as an empty array [].

{
  "section": "parameters",
  "summary": "string",
  "findings": [
    {
      "rule_id": "STRING_CONSTRAINT_MISSING",
      "section": "parameters",
      "severity": "error",
      "pointer": "paths./users/{userId}.get.parameters[0]",
      "message": "what is wrong",
      "suggested_fix": "how to fix it"
    }
  ]
}
