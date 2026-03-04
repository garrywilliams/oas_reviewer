"""
fact_builder.py
===============
Converts a parsed OpenAPI document into a flat, deterministic list of
"fact rows" for LLM consumption.

The LLM no longer receives raw OAS JSON or needs to resolve $refs.
It receives only flat rows with all leaf fields already extracted.

Fact kinds:
  - operation       : one row per path+method combination
  - parameter       : one row per parameter (path/query/header/cookie)
  - schema_property : one row per leaf property in component schemas
  - example_value   : one row per example value found

Output shape:
  {
    "facts": [ { "kind": "...", ... }, ... ]
  }

Or with hints envelope:
  {
    "hints": "...",
    "facts": [ ... ]
  }
"""
from __future__ import annotations

import copy
from typing import Any


# ── Public API ────────────────────────────────────────────────────────────────

def build_facts(resolved_spec: dict) -> dict:
    """
    Build a unified facts dict from a fully resolved OAS spec.

    Args:
        resolved_spec: Fully resolved OAS spec dict (from loader.load_oas_string).
                       $refs must already be resolved so leaf fields are accessible.

    Returns:
        {"facts": [...]} sorted deterministically.
    """
    builder = _FactBuilder(resolved_spec)
    return {"facts": builder.build()}


def build_facts_with_hints(resolved_spec: dict, hints_block: str) -> dict:
    """
    Build facts with a hints envelope for single-payload LLM calls.

    Args:
        resolved_spec: Fully resolved OAS spec dict.
        hints_block:   Pre-formatted hints string from payload.hints_block().

    Returns:
        {"hints": "...", "facts": [...]}
    """
    facts = build_facts(resolved_spec)
    return {"hints": hints_block, "facts": facts["facts"]}


def filter_facts(facts: list[dict], kinds: list[str]) -> list[dict]:
    """
    Filter a facts list to only the specified kinds.

    Args:
        facts: The full facts list from build_facts()["facts"].
        kinds: List of kind strings to include e.g. ["parameter", "operation"]

    Returns:
        Filtered list preserving sort order.
    """
    return [f for f in facts if f.get("kind") in kinds]


def filter_facts_by_param_location(facts: list[dict], location: str) -> list[dict]:
    """
    Filter parameter facts by their 'in' field.

    Args:
        facts:    Full facts list.
        location: One of: query, path, header, cookie

    Returns:
        Parameter facts matching the location.
    """
    return [
        f for f in facts
        if f.get("kind") == "parameter" and f.get("in") == location
    ]


# ── Fact builder class ────────────────────────────────────────────────────────

class _FactBuilder:

    HTTP_METHODS = ["get", "post", "put", "patch", "delete", "options", "head", "trace"]

    def __init__(self, spec: dict):
        self._spec = spec
        self._components = spec.get("components", {})

    def build(self) -> list[dict]:
        facts: list[dict] = []
        facts.extend(self._operation_facts())
        facts.extend(self._parameter_facts())
        facts.extend(self._schema_property_facts())
        facts.extend(self._example_value_facts())
        return self._sort(facts)

    # ── Operation facts ───────────────────────────────────────────────────────

    def _operation_facts(self) -> list[dict]:
        facts = []
        for path, path_item in self._spec.get("paths", {}).items():
            if not isinstance(path_item, dict):
                continue
            for method in self.HTTP_METHODS:
                op = path_item.get(method)
                if not isinstance(op, dict):
                    continue
                facts.append({
                    "kind": "operation",
                    "path": path,
                    "method": method.upper(),
                    "operationId": op.get("operationId") or None,
                    "summary": op.get("summary") or None,
                    "has_request_body": "requestBody" in op,
                    "tags": op.get("tags") or [],
                    "response_codes": sorted(op.get("responses", {}).keys()),
                    "pointer": f"paths.{path}.{method}",
                })
        return facts

    # ── Parameter facts ───────────────────────────────────────────────────────

    def _parameter_facts(self) -> list[dict]:
        facts = []

        # Component-level reusable parameters
        for name, param in self._components.get("parameters", {}).items():
            if isinstance(param, dict):
                facts.append(self._parameter_row(
                    param=param,
                    pointer=f"components.parameters.{name}",
                    path=None,
                    method=None,
                ))

        # Path and operation level
        for path, path_item in self._spec.get("paths", {}).items():
            if not isinstance(path_item, dict):
                continue

            for i, param in enumerate(path_item.get("parameters", [])):
                facts.append(self._parameter_row(
                    param=param,
                    pointer=f"paths.{path}.parameters[{i}]",
                    path=path,
                    method=None,
                ))

            for method in self.HTTP_METHODS:
                op = path_item.get(method)
                if not isinstance(op, dict):
                    continue
                for i, param in enumerate(op.get("parameters", [])):
                    facts.append(self._parameter_row(
                        param=param,
                        pointer=f"paths.{path}.{method}.parameters[{i}]",
                        path=path,
                        method=method.upper(),
                    ))

        return facts

    def _parameter_row(
        self,
        param: dict,
        pointer: str,
        path: str | None,
        method: str | None,
    ) -> dict:
        schema = param.get("schema", {}) or {}
        leaf = self._extract_leaf_fields(schema)

        row: dict = {
            "kind": "parameter",
            "path": path,
            "method": method,
            "name": param.get("name"),
            "in": param.get("in"),
            "required": param.get("required", False),
            "deprecated": param.get("deprecated", False),
            "description": param.get("description") or None,
            "pointer": pointer,
        }
        row.update(leaf)
        return row

    # ── Schema property facts ─────────────────────────────────────────────────

    def _schema_property_facts(self) -> list[dict]:
        facts = []
        schemas = self._components.get("schemas", {})

        for schema_name, schema in schemas.items():
            if not isinstance(schema, dict):
                continue
            self._walk_schema_properties(
                schema=schema,
                schema_name=schema_name,
                property_path="",
                pointer_prefix=f"components.schemas.{schema_name}",
                facts=facts,
                depth=0,
            )

        return facts

    def _walk_schema_properties(
        self,
        schema: dict,
        schema_name: str,
        property_path: str,
        pointer_prefix: str,
        facts: list[dict],
        depth: int,
    ) -> None:
        if depth > 8:
            return

        properties = schema.get("properties", {})
        for prop_name, prop_schema in properties.items():
            if not isinstance(prop_schema, dict):
                continue

            full_property_path = f"{property_path}.{prop_name}" if property_path else prop_name
            full_pointer = f"{pointer_prefix}.properties.{prop_name}"
            leaf = self._extract_leaf_fields(prop_schema)

            facts.append({
                "kind": "schema_property",
                "schema": schema_name,
                "property": full_property_path,
                "description": prop_schema.get("description") or None,
                "required": prop_name in schema.get("required", []),
                "nullable": prop_schema.get("nullable", False),
                "pointer": full_pointer,
                **leaf,
            })

            # Recurse into nested object properties
            prop_type = prop_schema.get("type")
            if prop_type == "object" or prop_schema.get("properties"):
                self._walk_schema_properties(
                    schema=prop_schema,
                    schema_name=schema_name,
                    property_path=full_property_path,
                    pointer_prefix=full_pointer,
                    facts=facts,
                    depth=depth + 1,
                )

            # Recurse into array items
            if prop_type == "array" and isinstance(prop_schema.get("items"), dict):
                items = prop_schema["items"]
                if items.get("properties"):
                    self._walk_schema_properties(
                        schema=items,
                        schema_name=schema_name,
                        property_path=f"{full_property_path}[]",
                        pointer_prefix=f"{full_pointer}.items",
                        facts=facts,
                        depth=depth + 1,
                    )

    # ── Example value facts ───────────────────────────────────────────────────

    def _example_value_facts(self) -> list[dict]:
        facts = []

        # Schema property examples
        schemas = self._components.get("schemas", {})
        for schema_name, schema in schemas.items():
            if not isinstance(schema, dict):
                continue
            for prop_name, prop_schema in schema.get("properties", {}).items():
                if not isinstance(prop_schema, dict):
                    continue
                if "example" in prop_schema:
                    pointer = f"components.schemas.{schema_name}.properties.{prop_name}"
                    facts.append({
                        "kind": "example_value",
                        "location": pointer,
                        "declared_type": prop_schema.get("type"),
                        "example_value": prop_schema["example"],
                        "pattern": prop_schema.get("pattern"),
                        "format": prop_schema.get("format"),
                        "pointer": pointer,
                    })

        # Parameter examples
        for path, path_item in self._spec.get("paths", {}).items():
            if not isinstance(path_item, dict):
                continue
            for method in self.HTTP_METHODS:
                op = path_item.get(method)
                if not isinstance(op, dict):
                    continue
                for i, param in enumerate(op.get("parameters", [])):
                    schema = param.get("schema", {}) or {}
                    if "example" in schema or "example" in param:
                        example_val = param.get("example") or schema.get("example")
                        pointer = f"paths.{path}.{method}.parameters[{i}]"
                        facts.append({
                            "kind": "example_value",
                            "location": pointer,
                            "declared_type": schema.get("type"),
                            "example_value": example_val,
                            "pattern": schema.get("pattern"),
                            "format": schema.get("format"),
                            "pointer": pointer,
                        })

        return facts

    # ── Leaf field extraction ($ref aware) ────────────────────────────────────

    def _extract_leaf_fields(
        self,
        schema: dict,
        _visited: frozenset | None = None,
        _depth: int = 0,
    ) -> dict:
        """
        Extract leaf validation fields from a schema, following $ref chains
        deterministically. Stops at depth 5 or on cycle detection.

        Returns a dict with keys:
            schema_type, pattern, format, enum, maxLength, minLength,
            minimum, maximum, example, is_ref, ref
        """
        if _visited is None:
            _visited = frozenset()

        if _depth > 5 or not isinstance(schema, dict):
            return self._empty_leaf()

        is_ref = False
        ref_str = None

        # Follow $ref chain
        if "$ref" in schema:
            ref_str = schema["$ref"]
            if ref_str in _visited:
                # Cycle — stop here
                leaf = self._empty_leaf()
                leaf["is_ref"] = True
                leaf["ref"] = ref_str
                return leaf

            resolved = self._resolve_ref(ref_str)
            if resolved is not None:
                is_ref = True
                return self._extract_leaf_fields(
                    resolved,
                    _visited=_visited | {ref_str},
                    _depth=_depth + 1,
                )
            else:
                leaf = self._empty_leaf()
                leaf["is_ref"] = True
                leaf["ref"] = ref_str
                return leaf

        # Handle allOf/anyOf/oneOf — merge first entry as best-effort
        for composition_key in ("allOf", "anyOf", "oneOf"):
            entries = schema.get(composition_key, [])
            if entries and isinstance(entries[0], dict):
                merged = {}
                for entry in entries:
                    merged.update(entry)
                return self._extract_leaf_fields(
                    merged,
                    _visited=_visited,
                    _depth=_depth + 1,
                )

        return {
            "schema_type": schema.get("type"),
            "pattern":     schema.get("pattern"),
            "format":      schema.get("format"),
            "enum":        schema.get("enum"),
            "maxLength":   schema.get("maxLength"),
            "minLength":   schema.get("minLength"),
            "minimum":     schema.get("minimum"),
            "maximum":     schema.get("maximum"),
            "example":     schema.get("example"),
            "is_ref":      is_ref,
            "ref":         ref_str,
        }

    def _resolve_ref(self, ref: str) -> dict | None:
        """Resolve an internal #/ reference against the spec."""
        if not ref.startswith("#/"):
            return None
        parts = ref[2:].split("/")
        target = self._spec
        try:
            for part in parts:
                part = part.replace("~1", "/").replace("~0", "~")
                target = target[part]
            return target if isinstance(target, dict) else None
        except (KeyError, TypeError):
            return None

    @staticmethod
    def _empty_leaf() -> dict:
        return {
            "schema_type": None,
            "pattern":     None,
            "format":      None,
            "enum":        None,
            "maxLength":   None,
            "minLength":   None,
            "minimum":     None,
            "maximum":     None,
            "example":     None,
            "is_ref":      False,
            "ref":         None,
        }

    # ── Sorting ───────────────────────────────────────────────────────────────

    @staticmethod
    def _sort(facts: list[dict]) -> list[dict]:
        """
        Sort facts deterministically:
        primary: kind, secondary: pointer, tertiary: name/property
        """
        def sort_key(f: dict) -> tuple:
            return (
                f.get("kind", ""),
                f.get("pointer", ""),
                f.get("name") or f.get("property") or "",
            )
        return sorted(facts, key=sort_key)
