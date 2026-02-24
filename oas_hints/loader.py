"""
OAS document loader.

Handles:
- YAML or JSON string input (no file required)
- Invalid date values (e.g. 31 April) that cause yaml.safe_load to fail
- $ref resolution via jsonref (for self-contained specs)
- Basic structural validation
"""
import json
import yaml
import jsonref


# ── Date-safe YAML loader ────────────────────────────────────────────────────
# YAML parsers try to coerce date-like strings into datetime objects.
# Invalid dates (e.g. 2025-04-31) cause a load failure.
# This loader strips the timestamp resolver so all dates stay as strings.

class _NoDatesSafeLoader(yaml.SafeLoader):
    pass

_NoDatesSafeLoader.yaml_implicit_resolvers = {
    key: [
        (tag, regexp)
        for tag, regexp in resolvers
        if tag not in ("tag:yaml.org,2002:timestamp",)
    ]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


# ── Public interface ─────────────────────────────────────────────────────────

def load_oas_string(content: str) -> tuple[dict | None, list[str]]:
    """
    Parse and resolve an OAS 3.x document from a YAML or JSON string.

    Automatically detects YAML vs JSON by attempting JSON first.
    Resolves all internal $ref entries so downstream code never sees them.

    Args:
        content: Raw YAML or JSON string of the OAS document.

    Returns:
        Tuple of (resolved_spec_dict, errors).
        resolved_spec_dict is None if loading failed.
        errors is a list of human-readable error strings (empty on success).
    """
    errors: list[str] = []
    raw_dict: dict | None = None

    # ── Step 1: parse string → dict ───────────────────────────────────────────
    stripped = content.strip()

    if stripped.startswith("{"):
        # Looks like JSON
        try:
            raw_dict = json.loads(stripped)
        except json.JSONDecodeError as e:
            errors.append(f"JSON parse failure: {e}")
            return None, errors
    else:
        # Treat as YAML (also handles JSON-in-YAML edge cases)
        try:
            raw_dict = yaml.load(stripped, Loader=_NoDatesSafeLoader)
        except yaml.YAMLError as e:
            errors.append(f"YAML parse failure: {e}")
            return None, errors

    if not isinstance(raw_dict, dict):
        errors.append("Parsed content is not a mapping — is this a valid OAS document?")
        return None, errors

    # ── Step 2: basic structural check ───────────────────────────────────────
    oas_version = raw_dict.get("openapi", "")
    if not oas_version:
        errors.append("Missing 'openapi' version field — is this an OAS 3.x document?")
        # Continue anyway; still useful to extract what we can
    elif not str(oas_version).startswith("3."):
        errors.append(f"'openapi' version is '{oas_version}' — only OAS 3.x is supported")

    # ── Step 3: resolve $refs ────────────────────────────────────────────────
    # jsonref.replace_refs works directly on dicts and handles internal refs.
    # For external file refs, prance would be needed instead.
    try:
        resolved = jsonref.replace_refs(raw_dict)
        # Force full materialisation by converting to plain dict
        resolved_dict = _deep_dict(resolved)
    except Exception as e:
        errors.append(f"$ref resolution failure: {e}")
        return raw_dict, errors  # return unresolved dict; better than nothing

    return resolved_dict, errors


def _deep_dict(obj):
    """
    Recursively convert a jsonref proxy object tree into plain Python dicts/lists.
    jsonref returns lazy proxy objects; this forces full evaluation.
    """
    if isinstance(obj, dict):
        return {k: _deep_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_dict(item) for item in obj]
    return obj
