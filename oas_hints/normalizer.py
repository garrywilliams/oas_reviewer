"""
normalizer.py
=============
Produces a compact, deterministic JSON representation of an OAS document
suitable for LLM prompt injection.

Key behaviours:
- $ref references are preserved exactly as written (NOT expanded)
- Keys are sorted alphabetically within each object for determinism
- Array order is preserved from the source document
- No new fields or wrapper structures are added
- Standard OAS top-level keys are emitted in a fixed order

This module works on the RAW (unresolved) spec dict from the loader.
The resolved spec is still used by hint extractors — this is only for
building the LLM prompt data payloads.
"""
from __future__ import annotations

import json

# Fixed top-level key order per OAS convention
_TOP_LEVEL_ORDER = ["openapi", "info", "servers", "tags", "paths", "components"]


def normalise_spec(raw_spec: dict) -> dict:
    """
    Normalise a raw (unresolved) OAS spec dict.

    Args:
        raw_spec: The parsed but NOT $ref-resolved spec dict from load_oas_string.

    Returns:
        A new dict with sorted keys and preserved $refs, ready for json.dumps.
    """
    return _normalise_value(raw_spec, top_level=True)


def extract_normalised_section(raw_spec: dict, section: str) -> list | dict:
    """
    Extract a specific section from the normalised spec for prompt injection.

    Args:
        raw_spec: Raw unresolved spec dict.
        section:  One of: "info", "paths", "operations", "schemas", "parameters"

    Returns:
        Normalised section data ready for json.dumps.
    """
    normalised = normalise_spec(raw_spec)

    if section == "info":
        return normalised.get("info", {})

    if section == "paths":
        return _extract_paths(normalised)

    if section == "operations":
        return _extract_operations(normalised)

    if section == "schemas":
        return normalised.get("components", {}).get("schemas", {})

    if section == "parameters":
        return _extract_parameters(normalised)

    raise ValueError(f"Unknown section: {section!r}")


def to_json(section_data, indent: int = 2) -> str:
    """Serialise normalised section data to a JSON string."""
    return json.dumps(section_data, indent=indent)


# ── Section extractors ────────────────────────────────────────────────────────

def _extract_paths(normalised: dict) -> dict:
    """Return paths object — structure only, $refs preserved."""
    return normalised.get("paths", {})


def _extract_operations(normalised: dict) -> list[dict]:
    """
    Return a flat list of operations with path and method context.
    $refs in requestBody, responses, and parameters are preserved.
    """
    operations = []
    http_methods = ["get", "post", "put", "patch", "delete", "options", "head", "trace"]

    for path, path_item in normalised.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method in http_methods:
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            operations.append({
                "path": path,
                "method": method,
                "operation": operation,
            })

    return operations


def _extract_parameters(normalised: dict) -> list[dict]:
    """
    Return a flat list of all parameters with location context.
    $refs in parameter schemas are preserved.
    """
    params = []
    http_methods = ["get", "post", "put", "patch", "delete", "options", "head", "trace"]

    # Components parameters
    for name, param in normalised.get("components", {}).get("parameters", {}).items():
        params.append({
            "scope": "component",
            "name": name,
            "parameter": param,
        })

    # Path and operation parameters
    for path, path_item in normalised.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue

        for p in path_item.get("parameters", []):
            params.append({
                "scope": "path-level",
                "path": path,
                "parameter": p,
            })

        for method in http_methods:
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            for p in operation.get("parameters", []):
                params.append({
                    "scope": "operation-level",
                    "path": path,
                    "method": method,
                    "operation_id": operation.get("operationId", ""),
                    "parameter": p,
                })

    return params


# ── Normalisation helpers ─────────────────────────────────────────────────────

def _normalise_value(value, top_level: bool = False):
    """Recursively normalise a value, sorting dict keys."""
    if isinstance(value, dict):
        return _normalise_dict(value, top_level=top_level)
    if isinstance(value, list):
        return [_normalise_value(item) for item in value]
    return value


def _normalise_dict(d: dict, top_level: bool = False) -> dict:
    """
    Return a new dict with keys sorted.

    If top_level=True, emit standard OAS top-level keys first in fixed order,
    then any remaining keys alphabetically.

    If the dict contains only a $ref key, return it as-is without sorting
    (preserves the $ref pointer exactly).
    """
    # Preserve $ref objects exactly — do not sort or modify
    if "$ref" in d:
        return {"$ref": d["$ref"]}

    if top_level:
        ordered = {}
        for key in _TOP_LEVEL_ORDER:
            if key in d:
                ordered[key] = _normalise_value(d[key])
        for key in sorted(d.keys()):
            if key not in ordered:
                ordered[key] = _normalise_value(d[key])
        return ordered

    return {k: _normalise_value(v) for k, v in sorted(d.items())}
