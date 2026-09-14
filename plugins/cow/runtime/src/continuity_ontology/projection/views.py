"""Derivative views: compact status, accessible HTML, SVG.

A view projects committed state. It never establishes it, so nothing here
returns a status that was not already in its semantic input, and a rendering
failure is recorded against the *view*, not against the claim it was going to
display.

Reuse is bound to the full semantic-input digest plus the rendering profile.
Two runs whose semantic inputs differ by one byte do not share a view, and a
view whose renderer version changed is regenerated rather than reused.

Accessibility is checked, not asserted. Status is carried by text as well as
colour, controlled vocabulary is never truncated, wide content scrolls inside
its own container rather than clipping, and the export is machine readable.
"""

from __future__ import annotations

import html
import json
from typing import Any, Iterable, Mapping, Sequence

from ..canonical.profiles import digest_with

__all__ = [
    "ViewError",
    "RendererUnavailable",
    "compact_status",
    "view_reuse_decision",
    "render_html_report",
    "render_status_svg",
    "accessibility_checks",
    "STATUS_SYMBOLS",
]

#: Text and shape carry status. Colour is redundant, never the only channel.
STATUS_SYMBOLS: dict[str, str] = {
    "PASS": "PASS ✓",
    "FAIL": "FAIL ✗",
    "UNKNOWN": "UNKNOWN ?",
    "ERROR": "ERROR !",
    "NOT_RUN": "NOT_RUN —",
}

_CONTROLLED_TERMS = frozenset(STATUS_SYMBOLS)


class ViewError(ValueError):
    """Base class for view failures."""


class RendererUnavailable(ViewError):
    """Raised when a required renderer backend is not importable."""


# ---------------------------------------------------------------------------
# Compact status
# ---------------------------------------------------------------------------

def compact_status(state: Mapping[str, Any], word_budget: int = 500) -> dict[str, Any]:
    """The default projection: compact, but never truncated past a blocker.

    The budget shapes prose. It does not shape the blocker list: if naming
    every blocker exceeds the budget, the budget is reported as exceeded and
    the blockers are still all there. Dropping a failure to hit a token target
    is the failure mode this guards against.
    """
    blockers = list(state.get("blockers", []))
    totals = dict(state.get("mandatoryTotals", {}))
    lines = [
        "state: " + str(state.get("lifecycle", "UNKNOWN")),
        "gate: " + str(state.get("currentGate", "none")),
        "mandatory checks: " + ", ".join(
            k + "=" + str(v) for k, v in sorted(totals.items())
        ) if totals else "mandatory checks: none recorded",
        "bundle: " + str(state.get("bundleDigest", "none")),
        "audit: " + str(state.get("auditDigest", "none")),
        "next legal action: " + str(state.get("nextLegalAction", "none")),
    ]
    for blocker in blockers:
        lines.append("blocker: " + str(blocker))
    for reference in state.get("evidenceReferences", []):
        lines.append("evidence: " + str(reference))

    text = "\n".join(lines)
    words = len(text.split())
    return {
        "recordType": "CompactStatus",
        "text": text,
        "wordCount": words,
        "wordBudget": word_budget,
        "budgetExceeded": words > word_budget,
        "blockerCount": len(blockers),
        "blockersNamed": [str(b) for b in blockers],
        "truncated": False,
        "note": (
            "Every blocker is named. Detailed evidence is retrieved by reference rather "
            "than inlined."
            + (
                " The word budget is exceeded because naming all blockers requires it;"
                " blockers are not dropped to meet a target."
                if words > word_budget
                else ""
            )
        ),
    }


# ---------------------------------------------------------------------------
# Reuse policy
# ---------------------------------------------------------------------------

def view_reuse_decision(
    semantic_input: Mapping[str, Any],
    profile_id: str,
    renderer_id: str,
    renderer_version: str,
    prior_view: Mapping[str, Any] | None,
    *,
    policy: str = "REUSE_IF_IDENTICAL",
    required_raw_capture: bool = False,
) -> dict[str, Any]:
    """Decide whether a prior view may be reused.

    ``NO_VIEW`` can suppress generating a *view*. It can never suppress a
    contract-required raw capture: those are evidence, and the policy has no
    authority over evidence.
    """
    digest = digest_with("continuity.core.v2", dict(semantic_input))

    if required_raw_capture:
        return {
            "recordType": "ViewDecision",
            "semanticInputDigest": digest,
            "reuse": False,
            "generate": True,
            "reason": (
                "a contract requires this raw capture as evidence; a view-reduction "
                "policy cannot waive required visual evidence"
            ),
            "requiredRawCapturePreserved": True,
        }

    if policy == "NO_VIEW":
        return {
            "recordType": "ViewDecision",
            "semanticInputDigest": digest,
            "reuse": False,
            "generate": False,
            "reason": "policy suppresses optional view generation",
            "requiredRawCapturePreserved": True,
        }

    if prior_view is None:
        return {
            "recordType": "ViewDecision",
            "semanticInputDigest": digest,
            "reuse": False,
            "generate": True,
            "reason": "no prior view exists for this semantic input",
        }

    mismatches: list[str] = []
    if prior_view.get("semanticInputDigest") != digest:
        mismatches.append("semantic input digest")
    if prior_view.get("profileId") != profile_id:
        mismatches.append("rendering profile")
    if prior_view.get("rendererId") != renderer_id:
        mismatches.append("renderer")
    if prior_view.get("rendererVersion") != renderer_version:
        mismatches.append("renderer version")
    if prior_view.get("lifecycle") == "WIP_DIAGNOSTIC":
        mismatches.append("prior view is a WIP diagnostic, not a committed projection")

    if mismatches:
        return {
            "recordType": "ViewDecision",
            "semanticInputDigest": digest,
            "reuse": False,
            "generate": True,
            "reason": "differs by: " + ", ".join(mismatches),
        }
    return {
        "recordType": "ViewDecision",
        "semanticInputDigest": digest,
        "reuse": True,
        "generate": False,
        "reason": "semantic input and rendering profile match exactly",
        "reusedViewId": prior_view.get("viewId"),
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _row(cells: Sequence[str], header: bool = False) -> str:
    tag = "th" if header else "td"
    scope = ' scope="row"' if not header else ' scope="col"'
    return "<tr>" + "".join(
        "<" + tag + (scope if index == 0 or header else "") + ">" + cell + "</" + tag + ">"
        for index, cell in enumerate(cells)
    ) + "</tr>"


def render_html_report(semantic_input: Mapping[str, Any]) -> dict[str, Any]:
    """Render an accessible, read-only, self-contained HTML report."""
    digest = digest_with("continuity.core.v2", dict(semantic_input))
    title = html.escape(str(semantic_input.get("title", "Continuity status")))

    sections: list[str] = []

    acceptance = semantic_input.get("acceptanceByDimension", [])
    if acceptance:
        rows = [_row(["Dimension", "Result", "Basis"], header=True)]
        for entry in acceptance:
            rows.append(
                _row(
                    [
                        html.escape(str(entry.get("dimension"))),
                        html.escape(STATUS_SYMBOLS.get(str(entry.get("status")), str(entry.get("status")))),
                        html.escape(str(entry.get("reason", ""))),
                    ]
                )
            )
        sections.append(
            '<section aria-labelledby="acceptance-h"><h2 id="acceptance-h">Acceptance dimensions</h2>'
            '<p>These are reported separately. One of them being satisfied says nothing about the others.</p>'
            '<div class="scroll"><table><caption>Release acceptance by dimension</caption>'
            + "".join(rows)
            + "</table></div></section>"
        )

    checks = semantic_input.get("checks", [])
    if checks:
        rows = [_row(["Check", "Result", "Reason", "Evidence"], header=True)]
        for check in checks:
            status = str(check.get("status"))
            rows.append(
                _row(
                    [
                        html.escape(str(check.get("checkId"))),
                        html.escape(STATUS_SYMBOLS.get(status, status)),
                        html.escape(str(check.get("reason", ""))),
                        html.escape(", ".join(check.get("evidenceRefs", [])) or "none"),
                    ]
                )
            )
        sections.append(
            '<section aria-labelledby="checks-h"><h2 id="checks-h">Mandatory checks</h2>'
            '<div class="filter"><label for="q">Filter checks</label>'
            '<input id="q" type="search" autocomplete="off"></div>'
            '<div class="scroll"><table id="checks"><caption>Per-check results</caption>'
            + "".join(rows)
            + "</table></div></section>"
        )

    resources = semantic_input.get("resources", [])
    if resources:
        rows = [_row(["Resource", "Basis", "Value", "Unit"], header=True)]
        for resource in resources:
            value = resource.get("value")
            rows.append(
                _row(
                    [
                        html.escape(str(resource.get("kind"))),
                        html.escape(str(resource.get("basis"))),
                        html.escape("not measured" if value is None else str(value)),
                        html.escape(str(resource.get("unit", ""))),
                    ]
                )
            )
        sections.append(
            '<section aria-labelledby="res-h"><h2 id="res-h">Resource accounting</h2>'
            '<p>An unmeasured resource shows as <em>not measured</em>. It is not zero.</p>'
            '<div class="scroll"><table><caption>Observed and unknown resources</caption>'
            + "".join(rows)
            + "</table></div></section>"
        )

    blockers = semantic_input.get("blockers", [])
    if blockers:
        sections.append(
            '<section aria-labelledby="blk-h"><h2 id="blk-h">Blockers</h2><ul>'
            + "".join("<li>" + html.escape(str(b)) + "</li>" for b in blockers)
            + "</ul></section>"
        )

    export = html.escape(json.dumps(semantic_input, indent=2, sort_keys=True))

    document = (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>" + title + "</title><style>"
        ":root{color-scheme:light dark}"
        "body{font:1rem/1.5 system-ui,sans-serif;margin:0 auto;max-width:70rem;padding:1.5rem}"
        "table{border-collapse:collapse;width:100%}"
        "caption{text-align:left;font-weight:600;padding:.4rem 0}"
        "th,td{border:1px solid currentColor;padding:.4rem .6rem;text-align:left;"
        "vertical-align:top;overflow-wrap:anywhere}"
        "code{overflow-wrap:anywhere}th{overflow-wrap:normal;word-break:normal}"
        ".scroll{overflow-x:auto}"
        "a:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid;outline-offset:2px}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere}"
        "</style></head><body>"
        '<a href="#main" class="skip">Skip to content</a>'
        "<h1>" + title + "</h1>"
        '<p><strong>Semantic input digest:</strong> <code>' + html.escape(digest) + "</code></p>"
        "<p>This page is a read-only projection of committed records. It displays state; "
        "it does not establish it, and nothing on it can cause a check to pass.</p>"
        '<main id="main">' + "".join(sections) + "</main>"
        '<section aria-labelledby="exp-h"><h2 id="exp-h">Machine-readable export</h2>'
        "<details><summary>Show the underlying record</summary>"
        "<pre>" + export + "</pre></details></section>"
        "<script>"
        "var q=document.getElementById('q');"
        "if(q){q.addEventListener('input',function(){"
        "var v=this.value.toLowerCase();"
        "var rows=document.querySelectorAll('#checks tr');"
        "for(var i=1;i<rows.length;i++){"
        "rows[i].hidden=v!==''&&rows[i].textContent.toLowerCase().indexOf(v)===-1;}});}"
        "</script>"
        "</body></html>"
    )

    return {
        "recordType": "ReviewView",
        "viewId": "html:" + digest[:20],
        "semanticInputDigest": digest,
        "profileId": "report.html.v1",
        "rendererId": "continuity_ontology.projection.views",
        "rendererVersion": "2.0.0",
        "lifecycle": "COMMITTED_PROJECTION"
        if semantic_input.get("committed", True)
        else "WIP_DIAGNOSTIC",
        "document": document,
        "accessibilityResults": accessibility_checks(document, semantic_input),
    }


def render_status_svg(semantic_input: Mapping[str, Any]) -> dict[str, Any]:
    """Render every check, FAIL first; long labels visibly abbreviate full title IDs."""
    checks = sorted(semantic_input.get("checks", []), key=lambda c: c.get("status") != "FAIL")
    width = max(240, 40 + 260 * min(len(checks), 4))
    height = 40 + 26 * ((len(checks) + 3) // 4)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + str(width) + " "
        + str(height) + '" role="img" aria-label="Check status summary">',
        "<title>Check status summary</title>",
    ]
    for index, check in enumerate(checks):
        column, row = index % 4, index // 4
        x, y = 12 + column * 260, 28 + row * 26
        status = str(check.get("status"))
        label = STATUS_SYMBOLS.get(status, status)
        full_id = str(check.get("checkId", ""))
        short_id = full_id if len(full_id) <= 18 else "…" + full_id[-18:]
        parts.append(
            '<text x="' + str(x) + '" y="' + str(y) + '" font-family="system-ui,sans-serif" '
            'font-size="12">'
            + "<title>" + html.escape(full_id) + "</title>" + html.escape(short_id) + ": " + html.escape(label)
            + "</text>"
        )
    parts.append("</svg>")
    return {
        "recordType": "ReviewView",
        "profileId": "status.svg.v1",
        "rendererId": "continuity_ontology.projection.views",
        "rendererVersion": "2.0.0",
        "document": "".join(parts),
        "lifecycle": "COMMITTED_PROJECTION",
    }


def render_raster(svg_document: str) -> dict[str, Any]:
    """Rasterize an SVG if a backend exists; otherwise report unavailable."""
    try:  # pragma: no cover - exercised only where a backend is installed
        import cairosvg  # type: ignore
    except ImportError:
        return {
            "recordType": "ReviewView",
            "profileId": "status.png.v1",
            "lifecycle": "UNAVAILABLE",
            "unavailableReason": (
                "no raster backend is importable; HTML is the complete report; SVG summarizes every check status. "
                "A missing renderer is an unavailable view, not a successful picture."
            ),
            "status": "UNKNOWN",
        }
    payload = cairosvg.svg2png(bytestring=svg_document.encode("utf-8"))
    return {
        "recordType": "ReviewView",
        "profileId": "status.png.v1",
        "lifecycle": "COMMITTED_PROJECTION",
        "rasterProfileDigest": digest_with("raw.file.sha256", payload),
        "status": "PASS",
    }


# ---------------------------------------------------------------------------
# Accessibility
# ---------------------------------------------------------------------------

def accessibility_checks(document: str, semantic_input: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Structural accessibility checks; absent documents are UNKNOWN.

    This does not establish browser keyboard, zoom or clipping behavior (R39).
    """
    if document is None:
        return [{"checkId": "a11y.document", "status": "UNKNOWN", "reason": "document not observed"}]
    results: list[dict[str, Any]] = []

    def check(check_id: str, ok: bool, reason: str) -> None:
        results.append({"checkId": check_id, "status": "PASS" if ok else "FAIL", "reason": reason})

    check("a11y.lang", 'lang="en"' in document, "the document declares a language")
    check("a11y.title", "<title>" in document, "the document has a title")
    check("a11y.viewport", 'name="viewport"' in document, "text scales on small viewports")
    check(
        "a11y.no_fixed_font_px",
        "font-size:10px" not in document and "font-size:8px" not in document,
        "no sub-scalable fixed font size",
    )
    check("a11y.focus_visible", "focus-visible" in document, "focus is visible for keyboard users")
    check("a11y.table_headers", "<th" in document or "<table" not in document,
          "tables use header cells")
    check("a11y.captions", "<caption>" in document or "<table" not in document,
          "tables are captioned")
    check("a11y.wide_content_scrolls", 'class="scroll"' in document or "<table" not in document,
          "wide tables scroll in their own container rather than clipping")

    statuses_in_input = {
        str(c.get("status"))
        for c in semantic_input.get("checks", [])
        if c.get("status") is not None
    }
    statuses_in_input |= {
        str(a.get("status"))
        for a in semantic_input.get("acceptanceByDimension", [])
        if a.get("status") is not None
    }
    missing = [
        status for status in sorted(statuses_in_input)
        if status in _CONTROLLED_TERMS and STATUS_SYMBOLS[status] not in document
    ]
    check(
        "a11y.status_text_not_colour",
        not missing,
        "every status appears as text"
        if not missing
        else "status(es) absent from the text: " + ", ".join(missing),
    )
    truncated = [
        term for term in sorted(statuses_in_input)
        if term in _CONTROLLED_TERMS and term[:4] + "…" in document
    ]
    check("a11y.no_truncated_vocabulary", not truncated,
          "controlled vocabulary is never abbreviated away")
    check("a11y.machine_export", "<pre>" in document,
          "a machine-readable export accompanies the rendering")
    check(
        "a11y.no_mutation_interface",
        "<form" not in document and "<button" not in document,
        "the report is read-only and offers no mutation interface",
    )
    return results
