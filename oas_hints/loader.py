"""
OAS document loader.

Handles:
- YAML or JSON string input (no file required)
- Invalid date values (e.g. 31 April) that cause yaml.safe_load to fail
- $ref resolution via jsonref (if installed) or inline resolver
- Returns BOTH the resolved spec (for hints) and raw spec (for normaliser)
- Basic structural validation
"""
import json
import yaml

try:
    import jsonref as _jsonref
    _HAS_JSONREF = True
except ImportError:
    _HAS_JSONREF = False


# ── Date-safe YAML loader ────────────────────────────────────────────────────

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
    Parse an OAS 3.x document from a YAML or JSON string.
    Returns the RESOLVED spec (all $refs expanded) for use with hint extractors.
    Use load_oas_string_raw() to get the unresolved spec for the normaliser.
    """
    raw_dict, errors = _parse(content)
    if raw_dict is None:
        return None, errors

    resolved = _resolve(raw_dict, errors)
    return resolved, errors


def load_oas_string_both(content: str) -> tuple[dict | None, dict | None, list[str]]:
    """
    Parse an OAS 3.x document and return BOTH versions.

    Returns:
        (resolved_spec, raw_spec, errors)

        resolved_spec — all $refs expanded, used by hint extractors
        raw_spec      — original structure with $refs intact, used by normaliser
    """
    raw_dict, errors = _parse(content)
    if raw_dict is None:
        return None, None, errors

    resolved = _resolve(raw_dict, errors)
    return resolved, raw_dict, errors


# ── Internal helpers ─────────────────────────────────────────────────────────

def _parse(content: str) -> tuple[dict | None, list[str]]:
    """Parse YAML or JSON string to a plain dict."""
    errors: list[str] = []
    stripped = content.strip()

    if stripped.startswith("{"):
        try:
            raw_dict = json.loads(stripped)
        except json.JSONDecodeError as e:
            errors.append(f"JSON parse failure: {e}")
            return None, errors
    else:
        try:
            raw_dict = yaml.load(stripped, Loader=_NoDatesSafeLoader)
        except yaml.YAMLError as e:
            errors.append(f"YAML parse failure: {e}")
            return None, errors

    if not isinstance(raw_dict, dict):
        errors.append("Parsed content is not a mapping — is this a valid OAS document?")
        return None, errors

    oas_version = raw_dict.get("openapi", "")
    if not oas_version:
        errors.append("Missing 'openapi' version field — is this an OAS 3.x document?")
    elif not str(oas_version).startswith("3."):
        errors.append(f"'openapi' version is '{oas_version}' — only OAS 3.x is supported")

    return raw_dict, errors


def _resolve(raw_dict: dict, errors: list[str]) -> dict:
    """Resolve all $refs in a parsed dict."""
    try:
        if _HAS_JSONREF:
            resolved = _jsonref.replace_refs(raw_dict)
            return _deep_dict(resolved)
        else:
            return _resolve_refs_inline(raw_dict, raw_dict)
    except Exception as e:
        errors.append(f"$ref resolution failure: {e}")
        return raw_dict


def _deep_dict(obj):
    if isinstance(obj, dict):
        return {k: _deep_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_dict(item) for item in obj]
    return obj


def _resolve_refs_inline(obj, root: dict, _depth: int = 0):
    """Simple internal $ref resolver for self-contained specs."""
    if _depth > 20:
        return obj
    if isinstance(obj, dict):
        if "$ref" in obj and isinstance(obj["$ref"], str):
            ref = obj["$ref"]
            if ref.startswith("#/"):
                parts = ref[2:].split("/")
                target = root
                for part in parts:
                    part = part.replace("~1", "/").replace("~0", "~")
                    target = target[part]
                return _resolve_refs_inline(target, root, _depth + 1)
        return {k: _resolve_refs_inline(v, root, _depth + 1) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_refs_inline(item, root, _depth + 1) for item in obj]
    return obj
