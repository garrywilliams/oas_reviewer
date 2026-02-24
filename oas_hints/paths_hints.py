"""
Hint extractor for the OAS `paths` section.

Covers path-level concerns: structure, naming conventions, path parameters
declared but not defined, duplicate paths, and trailing slash consistency.
Operation-level concerns are handled separately in operations_hints.py.
"""
import re
from .models import Hint, Severity, SectionPayload

SECTION = "paths"
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}


def extract_paths_hints(spec: dict) -> SectionPayload:
    """
    Extract hints from the `paths` object.

    Args:
        spec: Fully resolved OAS spec as a plain dict.

    Returns:
        SectionPayload with path-level hints and list of path entry dicts.
    """
    paths: dict = spec.get("paths", {})
    hints: list[Hint] = []
    raw_data = []

    if not paths:
        hints.append(Hint(
            section=SECTION, location="paths",
            severity=Severity.ERROR,
            message="paths object is empty or missing — no endpoints are defined",
            raw={}
        ))
        return SectionPayload(section=SECTION, hints=hints, raw_data=raw_data)

    seen_normalised: dict[str, str] = {}   # normalised path → original, for duplicate detection
    has_trailing_slash: list[str] = []
    no_trailing_slash: list[str] = []

    for path, path_item in paths.items():
        loc = f"paths.{path}"
        raw_data.append({"path": path, "path_item": path_item})

        # ── Path format ───────────────────────────────────────────────────────
        if not path.startswith("/"):
            hints.append(Hint(section=SECTION, location=loc, severity=Severity.ERROR,
                               message=f"path must start with '/': {path!r}"))

        if " " in path:
            hints.append(Hint(section=SECTION, location=loc, severity=Severity.ERROR,
                               message=f"path contains a space: {path!r}"))

        if re.search(r"[A-Z]", path.split("?")[0]):
            # Ignore path parameter names — they can be camelCase
            static_parts = re.sub(r"\{[^}]+\}", "", path)
            if re.search(r"[A-Z]", static_parts):
                hints.append(Hint(section=SECTION, location=loc, severity=Severity.WARNING,
                                   message=f"path contains uppercase characters in static segments (prefer kebab-case): {path!r}"))

        if path != "/" and path.endswith("/"):
            has_trailing_slash.append(path)
        else:
            no_trailing_slash.append(path)

        # ── Path parameter consistency ─────────────────────────────────────────
        # Parameters declared in the path template e.g. {userId}
        template_params = set(re.findall(r"\{([^}]+)\}", path))

        # Parameters defined at path-item level
        defined_params = {
            p.get("name")
            for p in path_item.get("parameters", [])
            if p.get("in") == "path"
        }
        # Also collect from each operation
        for method in HTTP_METHODS:
            op = path_item.get(method, {})
            if op:
                defined_params.update(
                    p.get("name")
                    for p in op.get("parameters", [])
                    if p.get("in") == "path"
                )

        missing = template_params - defined_params
        for mp in sorted(missing):
            hints.append(Hint(section=SECTION, location=loc, severity=Severity.ERROR,
                               message=f"path template uses '{{{mp}}}' but no path parameter named '{mp}' is defined"))

        extra = defined_params - template_params
        for ep in sorted(extra):
            hints.append(Hint(section=SECTION, location=loc, severity=Severity.WARNING,
                               message=f"parameter '{ep}' declared as in=path but '{{{ep}}}' does not appear in the path template"))

        # ── Duplicate path detection (normalised) ──────────────────────────────
        normalised = re.sub(r"\{[^}]+\}", "{}", path)
        if normalised in seen_normalised:
            hints.append(Hint(section=SECTION, location=loc, severity=Severity.WARNING,
                               message=(f"path may be a duplicate of '{seen_normalised[normalised]}' "
                                        f"after normalising path parameters")))
        else:
            seen_normalised[normalised] = path

        # ── HTTP method presence ───────────────────────────────────────────────
        defined_methods = [m for m in HTTP_METHODS if path_item.get(m)]
        if not defined_methods:
            hints.append(Hint(section=SECTION, location=loc, severity=Severity.WARNING,
                               message="path item has no HTTP method operations defined"))

    # ── Trailing slash consistency across all paths ───────────────────────────
    if has_trailing_slash and no_trailing_slash:
        hints.append(Hint(
            section=SECTION, location="paths",
            severity=Severity.WARNING,
            message=(f"inconsistent trailing slash usage: "
                     f"{len(has_trailing_slash)} path(s) have trailing slashes, "
                     f"{len(no_trailing_slash)} do not"),
            raw={}
        ))

    return SectionPayload(section=SECTION, hints=hints, raw_data=raw_data)
