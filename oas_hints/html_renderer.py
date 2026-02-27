"""
html_renderer.py
================
Renders a ValidationReport (or individual SectionValidationResult) to HTML.

Produces a clean, self-contained HTML report with:
  - Summary header (counts by severity)
  - Per-section collapsible grouping
  - Sortable findings table (Non-compliant | Severity | Suggested Fix)
  - Zero-findings notice when the section is clean
  - Inline CSS — no external dependencies
"""
from __future__ import annotations

from .validation_models import (
    ValidationReport,
    SectionValidationResult,
    Finding,
    Severity,
)

# ── Severity styling ──────────────────────────────────────────────────────────

_SEVERITY_BADGE = {
    Severity.ERROR:   '<span class="badge badge-error">ERROR</span>',
    Severity.WARNING: '<span class="badge badge-warning">WARNING</span>',
    Severity.INFO:    '<span class="badge badge-info">INFO</span>',
}

_CSS = """
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         font-size: 14px; color: #1a1a2e; background: #f8f9fa; margin: 0; padding: 24px; }
  h1   { font-size: 22px; margin-bottom: 4px; }
  .meta { color: #666; font-size: 13px; margin-bottom: 24px; }

  /* Summary bar */
  .summary-bar { display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; }
  .summary-card { background: #fff; border-radius: 8px; padding: 12px 20px;
                  box-shadow: 0 1px 4px rgba(0,0,0,.08); min-width: 120px; }
  .summary-card .count { font-size: 28px; font-weight: 700; line-height: 1; }
  .summary-card .label { font-size: 12px; color: #888; margin-top: 2px; }
  .count-error   { color: #c0392b; }
  .count-warning { color: #d35400; }
  .count-info    { color: #2471a3; }
  .count-total   { color: #1a1a2e; }

  /* Section blocks */
  .section { background: #fff; border-radius: 8px; margin-bottom: 20px;
             box-shadow: 0 1px 4px rgba(0,0,0,.08); overflow: hidden; }
  .section-header { padding: 14px 20px; background: #f0f2f5; display: flex;
                    justify-content: space-between; align-items: center;
                    border-bottom: 1px solid #e0e0e0; }
  .section-title  { font-weight: 600; font-size: 15px; text-transform: uppercase;
                    letter-spacing: .05em; }
  .section-counts { font-size: 12px; color: #555; }
  .section-summary { padding: 10px 20px; font-size: 13px; color: #555;
                     border-bottom: 1px solid #f0f0f0; font-style: italic; }
  .clean-notice   { padding: 16px 20px; color: #27ae60; font-size: 13px; }

  /* Table */
  table   { width: 100%; border-collapse: collapse; }
  thead th { background: #f0f2f5; padding: 10px 16px; text-align: left;
             font-size: 12px; text-transform: uppercase; letter-spacing: .05em;
             color: #555; border-bottom: 2px solid #dde; white-space: nowrap; }
  tbody tr:hover { background: #fafbff; }
  tbody td { padding: 10px 16px; border-bottom: 1px solid #eef; vertical-align: top; }
  td.pointer { font-family: 'SF Mono', 'Fira Code', monospace; font-size: 12px;
               color: #555; white-space: nowrap; max-width: 360px;
               overflow: hidden; text-overflow: ellipsis; }
  td.message  { max-width: 380px; }
  td.fix      { max-width: 300px; color: #27ae60; }
  .rule-label { font-size: 11px; font-weight: 600; color: #888;
                display: block; margin-bottom: 2px; }

  /* Badges */
  .badge { display: inline-block; padding: 2px 8px; border-radius: 4px;
           font-size: 11px; font-weight: 700; white-space: nowrap; }
  .badge-error   { background: #fdecea; color: #c0392b; }
  .badge-warning { background: #fef3e2; color: #d35400; }
  .badge-info    { background: #eaf4fb; color: #2471a3; }
</style>
"""


# ── Public API ────────────────────────────────────────────────────────────────

def render_report(report: ValidationReport) -> str:
    """
    Render a complete ValidationReport to a self-contained HTML string.

    Args:
        report: Assembled ValidationReport from all section results.

    Returns:
        Full HTML document as a string.
    """
    body_parts = [
        _CSS,
        _render_header(report),
        _render_summary_bar(report),
    ]

    for section_name, result in report.sections.items():
        body_parts.append(_render_section_block(result))

    return "\n".join(body_parts)


def render_findings_table(result: SectionValidationResult) -> str:
    """
    Render just the findings table rows for a single section.
    Useful if you want to embed the table fragment into your own template.

    Args:
        result: A single SectionValidationResult.

    Returns:
        HTML string containing <tr> elements only (no wrapping table tags).
    """
    if not result.findings:
        return ""
    return "\n".join(_render_finding_row(f) for f in result.findings)


def render_section_block(result: SectionValidationResult) -> str:
    """
    Render a single section block (header + table) as an HTML fragment.
    """
    return _render_section_block(result)


# ── Internal renderers ────────────────────────────────────────────────────────

def _render_header(report: ValidationReport) -> str:
    return f"""
<h1>OAS Validation Report</h1>
<div class="meta">
  <strong>{_esc(report.spec_title)}</strong> &nbsp;v{_esc(report.spec_version)}
</div>"""


def _render_summary_bar(report: ValidationReport) -> str:
    total = len(report.all_findings)
    return f"""
<div class="summary-bar">
  <div class="summary-card">
    <div class="count count-total">{total}</div>
    <div class="label">Total findings</div>
  </div>
  <div class="summary-card">
    <div class="count count-error">{report.total_errors}</div>
    <div class="label">Errors</div>
  </div>
  <div class="summary-card">
    <div class="count count-warning">{report.total_warnings}</div>
    <div class="label">Warnings</div>
  </div>
  <div class="summary-card">
    <div class="count count-info">{report.total_info}</div>
    <div class="label">Info</div>
  </div>
</div>"""


def _render_section_block(result: SectionValidationResult) -> str:
    section_label = result.section.upper()
    counts = (
        f"{result.error_count}E &nbsp; {result.warning_count}W &nbsp; {result.info_count}I"
    )

    summary_html = ""
    if result.summary:
        summary_html = f'<div class="section-summary">{_esc(result.summary)}</div>'

    if not result.findings:
        content = '<div class="clean-notice">✓ No violations found in this section.</div>'
    else:
        rows = "\n".join(_render_finding_row(f) for f in result.findings)
        content = f"""
<table>
  <thead>
    <tr>
      <th style="width:40%">Non-compliant</th>
      <th style="width:8%">Severity</th>
      <th style="width:52%">Suggested Fix</th>
    </tr>
  </thead>
  <tbody>
{rows}
  </tbody>
</table>"""

    return f"""
<div class="section">
  <div class="section-header">
    <span class="section-title">{section_label}</span>
    <span class="section-counts">{counts}</span>
  </div>
  {summary_html}
  {content}
</div>"""


def _render_finding_row(finding: Finding) -> str:
    badge = _SEVERITY_BADGE.get(finding.severity, finding.severity)
    label = _esc(finding.label())
    pointer = _esc(finding.pointer)
    message = _esc(finding.message)
    fix = _esc(finding.suggested_fix)

    return f"""    <tr>
      <td class="message">
        <span class="rule-label">{label}</span>
        <span class="pointer-inline" title="{pointer}">{pointer}</span><br>
        {message}
      </td>
      <td>{badge}</td>
      <td class="fix">{fix}</td>
    </tr>"""


def _esc(text: str) -> str:
    """Minimal HTML escaping."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
