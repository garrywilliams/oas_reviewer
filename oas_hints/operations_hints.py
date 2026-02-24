"""
Hint extractor for OAS operations (path + method combinations).

Covers: operationId, summary, description, tags, request bodies,
response coverage, deprecated usage, and security.
"""
from .models import Hint, Severity, SectionPayload

SECTION = "operations"
HTTP_METHODS = ["get", "post", "put", "patch", "delete", "options", "head", "trace"]

# HTTP methods that should generally not have a request body
NO_BODY_METHODS = {"get", "delete", "head", "options", "trace"}


def extract_operations_hints(spec: dict) -> SectionPayload:
    """
    Extract hints from all operations across all paths.

    Args:
        spec: Fully resolved OAS spec as a plain dict.

    Returns:
        SectionPayload with operation-level hints and list of operation entry dicts.
    """
    paths: dict = spec.get("paths", {})
    hints: list[Hint] = []
    raw_data: list[dict] = []

    seen_operation_ids: dict[str, str] = {}  # operationId → first location seen

    for path, path_item in paths.items():
        for method in HTTP_METHODS:
            operation: dict = path_item.get(method)
            if not operation:
                continue

            loc = f"paths.{path}.{method}"
            raw_data.append({"path": path, "method": method, "operation": operation})

            operation_id = operation.get("operationId", "")
            summary = operation.get("summary", "")
            description = operation.get("description", "")
            tags = operation.get("tags", [])
            responses: dict = operation.get("responses", {})
            request_body = operation.get("requestBody")
            deprecated = operation.get("deprecated", False)
            security = operation.get("security")  # None means inherit, [] means unsecured

            # ── operationId ───────────────────────────────────────────────────
            if not operation_id:
                hints.append(Hint(section=SECTION, location=loc, severity=Severity.ERROR,
                                   message="operationId is missing — required for SDK generation and tooling"))
            else:
                if operation_id in seen_operation_ids:
                    hints.append(Hint(section=SECTION, location=loc, severity=Severity.ERROR,
                                       message=(f"operationId '{operation_id}' is duplicated "
                                                f"(first seen at {seen_operation_ids[operation_id]})")))
                else:
                    seen_operation_ids[operation_id] = loc

                import re
                if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", operation_id):
                    hints.append(Hint(section=SECTION, location=loc, severity=Severity.WARNING,
                                       message=f"operationId '{operation_id}' contains unusual characters"))

            # ── Summary ───────────────────────────────────────────────────────
            if not summary:
                hints.append(Hint(section=SECTION, location=loc, severity=Severity.WARNING,
                                   message="summary is missing"))
            else:
                if len(summary) > 120:
                    hints.append(Hint(section=SECTION, location=loc, severity=Severity.WARNING,
                                       message=f"summary is long ({len(summary)} chars) — summaries should be concise"))
                if summary.endswith("."):
                    hints.append(Hint(section=SECTION, location=loc, severity=Severity.INFO,
                                       message=f"summary ends with a period — convention is to omit it"))
                if summary[0].islower():
                    hints.append(Hint(section=SECTION, location=loc, severity=Severity.WARNING,
                                       message=f"summary starts with lowercase: {summary!r}"))

            # ── Description ───────────────────────────────────────────────────
            if not description and not summary:
                hints.append(Hint(section=SECTION, location=loc, severity=Severity.WARNING,
                                   message="neither summary nor description is provided"))

            # ── Tags ──────────────────────────────────────────────────────────
            if not tags:
                hints.append(Hint(section=SECTION, location=loc, severity=Severity.WARNING,
                                   message="no tags assigned — operations should be tagged for grouping in documentation"))
            else:
                # Check that used tags are declared at the top level
                declared_tags = {t.get("name") for t in spec.get("tags", [])}
                for tag in tags:
                    if declared_tags and tag not in declared_tags:
                        hints.append(Hint(section=SECTION, location=loc, severity=Severity.WARNING,
                                           message=f"tag '{tag}' is used but not declared in the top-level tags object"))

            # ── Responses ─────────────────────────────────────────────────────
            if not responses:
                hints.append(Hint(section=SECTION, location=loc, severity=Severity.ERROR,
                                   message="responses object is missing or empty"))
            else:
                status_codes = list(responses.keys())

                if "default" not in status_codes:
                    has_5xx = any(str(c).startswith("5") for c in status_codes)
                    if not has_5xx:
                        hints.append(Hint(section=SECTION, location=loc, severity=Severity.WARNING,
                                           message="no default response or 5xx error response defined"))

                if method in ("post", "put") and "400" not in status_codes:
                    hints.append(Hint(section=SECTION, location=loc, severity=Severity.WARNING,
                                       message=f"{method.upper()} operation has no 400 Bad Request response defined"))

                if method == "post" and "201" not in status_codes and "200" not in status_codes:
                    hints.append(Hint(section=SECTION, location=loc, severity=Severity.INFO,
                                       message="POST operation has neither 200 nor 201 success response"))

                for code, response in responses.items():
                    if not response.get("description"):
                        hints.append(Hint(section=SECTION, location=f"{loc}.responses.{code}",
                                           severity=Severity.ERROR,
                                           message=f"response {code} is missing a description (required by OAS)"))

            # ── Request body ──────────────────────────────────────────────────
            if request_body and method in NO_BODY_METHODS:
                hints.append(Hint(section=SECTION, location=loc, severity=Severity.WARNING,
                                   message=f"{method.upper()} operation defines a requestBody — this is semantically unusual"))

            if method in ("post", "put", "patch") and not request_body:
                hints.append(Hint(section=SECTION, location=loc, severity=Severity.INFO,
                                   message=f"{method.upper()} operation has no requestBody — intentional?"))

            # ── Deprecated ────────────────────────────────────────────────────
            if deprecated:
                hints.append(Hint(section=SECTION, location=loc, severity=Severity.INFO,
                                   message="operation is marked deprecated"))

            # ── Security ─────────────────────────────────────────────────────
            if security == []:
                hints.append(Hint(section=SECTION, location=loc, severity=Severity.INFO,
                                   message="operation explicitly opts out of security (security: []) — intentional?"))

    return SectionPayload(section=SECTION, hints=hints, raw_data=raw_data)
