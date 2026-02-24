"""
Hint extractor for the OAS `info` section.

Covers: title, version, description, contact, license, terms of service.
"""
from .models import Hint, Severity, SectionPayload

SECTION = "info"


def extract_info_hints(spec: dict) -> SectionPayload:
    """
    Extract hints from the top-level `info` object.

    Args:
        spec: Fully resolved OAS spec as a plain dict.

    Returns:
        SectionPayload containing hints and the raw info dict.
    """
    info = spec.get("info", {})
    hints: list[Hint] = []

    def hint(severity: Severity, message: str) -> Hint:
        return Hint(section=SECTION, location="info", severity=severity, message=message, raw=info)

    # ── Title ────────────────────────────────────────────────────────────────
    title = info.get("title", "")
    if not title:
        hints.append(hint(Severity.ERROR, "title is missing"))
    else:
        if title != title.strip():
            hints.append(hint(Severity.WARNING, f"title has leading/trailing whitespace: {title!r}"))
        if len(title) < 5:
            hints.append(hint(Severity.WARNING, f"title is very short ({len(title)} chars): {title!r}"))
        if title[0].islower():
            hints.append(hint(Severity.WARNING, f"title starts with lowercase: {title!r}"))
        # Detect version numbers embedded in title (common anti-pattern)
        import re
        if re.search(r"v\d+|version\s*\d+|\d+\.\d+", title, re.IGNORECASE):
            hints.append(hint(Severity.WARNING, f"title appears to contain a version number — use the `version` field instead: {title!r}"))

    # ── Version ──────────────────────────────────────────────────────────────
    version = info.get("version", "")
    if not version:
        hints.append(hint(Severity.ERROR, "version is missing"))
    else:
        version_str = str(version)
        import re
        if not re.match(r"^\d+\.\d+(\.\d+)?$", version_str):
            hints.append(hint(Severity.WARNING, f"version does not follow semantic versioning (major.minor.patch): {version_str!r}"))

    # ── Description ──────────────────────────────────────────────────────────
    description = info.get("description", "")
    if not description:
        hints.append(hint(Severity.WARNING, "description is missing — consider adding a summary of the API's purpose"))
    elif len(description) < 20:
        hints.append(hint(Severity.WARNING, f"description is very short ({len(description)} chars) — may not be useful to consumers"))

    # ── Contact ───────────────────────────────────────────────────────────────
    contact = info.get("contact")
    if contact is None:
        hints.append(hint(Severity.INFO, "contact object is absent — recommended for production APIs"))
    else:
        if not contact.get("name") and not contact.get("email"):
            hints.append(hint(Severity.WARNING, "contact object is present but has no name or email"))
        email = contact.get("email", "")
        if email and "@" not in email:
            hints.append(hint(Severity.ERROR, f"contact.email does not look like a valid email address: {email!r}"))

    # ── License ───────────────────────────────────────────────────────────────
    license_obj = info.get("license")
    if license_obj is None:
        hints.append(hint(Severity.INFO, "license object is absent"))
    else:
        if not license_obj.get("name"):
            hints.append(hint(Severity.ERROR, "license.name is required when license object is present"))

    # ── Terms of Service ──────────────────────────────────────────────────────
    tos = info.get("termsOfService", "")
    if tos:
        import re
        if not re.match(r"https?://", tos):
            hints.append(hint(Severity.WARNING, f"termsOfService should be a URL: {tos!r}"))

    return SectionPayload(section=SECTION, hints=hints, raw_data=info)
