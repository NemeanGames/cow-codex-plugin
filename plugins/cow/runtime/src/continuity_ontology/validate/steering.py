"""Scan agent steering files as untrusted input.

AGENTS.md, CLAUDE.md and skill files are instructions an agent will follow at
cold start, often without a human reading them first. That makes them the
cheapest place to plant a payload: a fork or a pull request that adds one line
to AGENTS.md is executed by every agent that trusts the file. So the file is
treated as hostile until scanned, and the scan is deterministic, offline and
stdlib-only so it can run before anything else does.

What it looks for, and why each is a signal rather than noise:

* **remote_exec** -- ``curl … | sh``, ``iwr … | iex``. There is no legitimate
  reason for a steering file to fetch and run code.
* **encoded_payload** -- base64 decode calls and long base64 runs. Encoding is
  how a payload avoids the pattern above.
* **hidden_unicode** -- zero-width and bidi-override characters. Invisible when
  rendered, present when read by a model.
* **hidden_comment** -- HTML comments other than the declared rule markers.
  Comments are invisible in rendered Markdown and visible to the agent.
* **override_phrase** -- "ignore previous instructions", "the user has already
  authorized", "do not tell the user". Steering files describe a repository;
  they do not renegotiate the agent's authority.
* **credential_access** -- ``~/.ssh``, ``.aws/credentials``, keychain reads.
* **external_url** -- any URL. This repository is self-contained; a steering
  file that points elsewhere is asking the agent to leave.
* **dangerous_flag** -- ``--no-verify``, ``sudo``, ``rm -rf``, force pushes.
* **non_ascii_in_code** -- a Cyrillic ``а`` in ``pаthon`` runs something else.
* **unknown_command** -- a repository command the repository does not contain.
* **oversized** -- a steering file past the size bound. Large files hide
  things and burn the cold-start tokens they were meant to save.

Findings are reported with the line and a short sample. The scan never
modifies a file.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ..canonical.profiles import digest_with

__all__ = [
    "DEFAULT_STEERING_FILES",
    "MAX_STEERING_BYTES",
    "scan_text",
    "scan_file",
    "scan_repository",
]

#: The steering files this repository ships. Any of them may be absent.
DEFAULT_STEERING_FILES: tuple[str, ...] = (
    "AGENTS.md",
    "CLAUDE.md",
    ".claude/skills/ont20/SKILL.md",
    "AGENT_BOOTSTRAP_v4.1.md",
)

#: A steering file should be read in full at cold start. Past this it is
#: either padding or hiding something, and either wastes the tokens it exists
#: to save.
MAX_STEERING_BYTES = 32 * 1024

#: The one HTML comment form the files are allowed to carry.
_ALLOWED_COMMENT = re.compile(r"^<!-- RULES-(?:BEGIN[^>]*|END) -->$")

_REMOTE_EXEC = re.compile(
    r"\b(?:curl|wget|iwr|invoke-webrequest|invoke-restmethod|fetch)\b[^\n|]*\|\s*"
    r"(?:sh|bash|zsh|dash|ksh|python\d?|perl|ruby|node|iex|invoke-expression|pwsh|powershell)\b"
    r"|\biex\s*\(|\binvoke-expression\b|\beval\s*[\"'(]?\s*\$\(\s*(?:curl|wget)",
    flags=re.IGNORECASE,
)
_ENCODED = re.compile(
    r"\bbase64\s+(?:-d|--decode|-D)\b|\[convert\]::frombase64string|"
    r"\bbase64\.b64decode\b|(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{64,}={0,2}(?![A-Za-z0-9+/=])",
    flags=re.IGNORECASE,
)
_HIDDEN_UNICODE = re.compile("[\u200b\u200c\u200d\u2060\u2061\u2062\u2063\u2064\ufeff\u202a-\u202e\u2066-\u2069\u00ad]")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_OVERRIDE = re.compile(
    r"\bignore\s+(?:all\s+|any\s+)?(?:previous|prior|above|earlier|the)\s+(?:instructions|rules|guidance)\b"
    r"|\bdisregard\s+(?:your|the|all|any)\s+(?:previous|prior|system|earlier)\b"
    r"|\byou\s+are\s+now\s+(?:a|an|the|in)\b"
    r"|\bnew\s+instructions?\s*:"
    r"|\bsystem\s+prompt\b"
    r"|\bthe\s+user\s+has\s+(?:already\s+)?(?:authorized|approved|consented|agreed)\b"
    r"|\bdo\s+not\s+(?:tell|inform|notify|warn)\s+the\s+user\b"
    r"|\bwithout\s+(?:asking|telling|informing)\s+(?:the\s+)?user\b"
    r"|\bact\s+as\s+(?:root|admin|administrator|the\s+system)\b"
    r"|\bthis\s+overrides?\s+(?:all|any|your)\b",
    flags=re.IGNORECASE,
)
_CREDENTIAL = re.compile(
    r"~/\.ssh\b|\.ssh/id_[a-z0-9]+|\.aws/credentials|\.netrc\b|\.git-credentials\b"
    r"|\bget-credential\b|security\s+find-(?:generic|internet)-password"
    r"|\bkeychain\b|\.docker/config\.json|\bgh\s+auth\s+token\b"
    r"|\$env:[A-Z_]*(?:TOKEN|KEY|SECRET|PASSWORD)|\$\{?[A-Z_]*(?:TOKEN|KEY|SECRET|PASSWORD)\}?\b",
    flags=re.IGNORECASE,
)
_URL = re.compile(r"\b(?:https?|ftp|ssh|git)://[^\s)>\]\"']+")
_DANGEROUS = re.compile(
    r"--no-verify\b|--dangerously|dangerouslyDisableSandbox|--no-gpg-sign"
    r"|(?:^|[\s;&|])sudo\s|\bchmod\s+(?:-R\s+)?777\b"
    r"|\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+(?:/|~|\$HOME|\*|\.\.)"
    r"|remove-item\b[^\n]*-recurse[^\n]*(?:C:\\|\$env:USERPROFILE|~)"
    r"|\bgit\s+push\b[^\n]*(?:--force\b|-f\b)|\bgit\s+reset\s+--hard\s+origin"
    r"|\bgit\s+(?:filter-branch|filter-repo)\b|\bformat-volume\b|\bmkfs\.",
    flags=re.IGNORECASE | re.MULTILINE,
)
_FENCE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_REPO_COMMAND = re.compile(
    r"(?:python\d?|\.venv[/\\]Scripts[/\\]python(?:\.exe)?)\s+(?:-m\s+([A-Za-z_][\w.]*)|(scripts/[\w/.-]+\.py))"
)

_CATEGORY_DOC = {
    "remote_exec": "fetches and executes remote code",
    "encoded_payload": "carries or decodes an encoded payload",
    "hidden_unicode": "contains invisible or direction-override characters",
    "hidden_comment": "contains an HTML comment other than the declared rule markers",
    "override_phrase": "attempts to renegotiate the agent's instructions or authority",
    "credential_access": "references credential material",
    "external_url": "points outside the repository",
    "dangerous_flag": "instructs a safety bypass or destructive operation",
    "non_ascii_in_code": "has a non-ASCII character inside a command or code span",
    "unknown_command": "tells the agent to run something this repository does not contain",
    "oversized": "exceeds the steering-file size bound",
}


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _finding(category: str, line: int, sample: str) -> dict[str, Any]:
    return {
        "category": category,
        "line": line,
        "sample": sample.replace("\n", "\\n")[:80],
        "why": _CATEGORY_DOC[category],
    }


def scan_text(
    text: str,
    *,
    repo_root: str | os.PathLike[str] | None = None,
    allowed_urls: Sequence[str] = (),
) -> list[dict[str, Any]]:
    """Scan one steering document. Returns findings; an empty list is clean."""
    findings: list[dict[str, Any]] = []

    if len(text.encode("utf-8")) > MAX_STEERING_BYTES:
        findings.append(_finding("oversized", 1, str(len(text.encode("utf-8"))) + " bytes"))

    for match in _REMOTE_EXEC.finditer(text):
        findings.append(_finding("remote_exec", _line_of(text, match.start()), match.group(0)))

    for match in _ENCODED.finditer(text):
        run = match.group(0)
        # A long run is only suspicious if it could be base64 rather than a
        # digest. Hex digests -- either case -- appear legitimately in every
        # steering file that tells an agent what to verify, and the hex
        # alphabet cannot carry a base64 payload.
        if len(run) >= 64 and all(c in "0123456789abcdefABCDEF" for c in run.strip("=")):
            continue
        findings.append(_finding("encoded_payload", _line_of(text, match.start()), run))

    for match in _HIDDEN_UNICODE.finditer(text):
        # A BOM at byte zero is an encoding artefact, not a hiding place.
        if match.start() == 0 and match.group(0) == "\ufeff":
            continue
        findings.append(
            _finding("hidden_unicode", _line_of(text, match.start()), "U+%04X" % ord(match.group(0)))
        )

    for match in _HTML_COMMENT.finditer(text):
        if not _ALLOWED_COMMENT.match(match.group(0).strip()):
            findings.append(_finding("hidden_comment", _line_of(text, match.start()), match.group(0)))

    for match in _OVERRIDE.finditer(text):
        findings.append(_finding("override_phrase", _line_of(text, match.start()), match.group(0)))

    for match in _CREDENTIAL.finditer(text):
        findings.append(_finding("credential_access", _line_of(text, match.start()), match.group(0)))

    for match in _URL.finditer(text):
        url = match.group(0)
        if any(url.startswith(prefix) for prefix in allowed_urls):
            continue
        findings.append(_finding("external_url", _line_of(text, match.start()), url))

    for match in _DANGEROUS.finditer(text):
        findings.append(_finding("dangerous_flag", _line_of(text, match.start()), match.group(0)))

    code_regions: list[tuple[int, str]] = [(m.start(), m.group(0)) for m in _FENCE.finditer(text)]
    stripped = _FENCE.sub(lambda m: " " * len(m.group(0)), text)
    code_regions += [(m.start(1), m.group(1)) for m in _INLINE_CODE.finditer(stripped)]
    for start, region in code_regions:
        for offset, char in enumerate(region):
            if ord(char) > 0x7F:
                findings.append(
                    _finding("non_ascii_in_code", _line_of(text, start + offset),
                             "U+%04X in %r" % (ord(char), region[max(0, offset - 12): offset + 12]))
                )
                break

    if repo_root is not None:
        root = Path(repo_root)
        for match in _REPO_COMMAND.finditer(text):
            module, script = match.group(1), match.group(2)
            if script:
                if not (root / script).exists():
                    findings.append(_finding("unknown_command", _line_of(text, match.start()), script))
            elif module:
                if module in ("pytest", "pip", "venv", "http.server", "json.tool"):
                    continue
                candidate = root / "src" / Path(*module.split("."))
                if not (candidate.with_suffix(".py").exists() or (candidate / "__init__.py").exists()):
                    findings.append(_finding("unknown_command", _line_of(text, match.start()), module))

    findings.sort(key=lambda f: (f["line"], f["category"], f["sample"]))
    return findings


def scan_file(
    path: str | os.PathLike[str],
    *,
    repo_root: str | os.PathLike[str] | None = None,
    allowed_urls: Sequence[str] = (),
) -> dict[str, Any]:
    """Scan one file. ``repo_root`` is where referenced commands are resolved."""
    target = Path(path)
    raw = target.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    findings = scan_text(text, repo_root=repo_root, allowed_urls=allowed_urls)
    return {
        "path": str(target).replace("\\", "/"),
        "bytes": len(raw),
        "digest": digest_with("raw.file.sha256", raw),
        "findings": findings,
        "clean": not findings,
    }


def scan_repository(
    repo_root: str | os.PathLike[str],
    files: Iterable[str] = DEFAULT_STEERING_FILES,
    *,
    allowed_urls: Sequence[str] = (),
    command_root: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Scan every steering file present and return one receipt.

    ``repo_root`` is where the files are read from. ``command_root`` is where
    the commands they mention are resolved; it defaults to ``repo_root``. The
    two differ when scanning a built payload copy, which carries the steering
    files but not the scripts they refer to -- resolving against the copy
    would report every script as unknown.
    """
    root = Path(repo_root)
    commands_in = Path(command_root) if command_root is not None else root
    results: list[dict[str, Any]] = []
    absent: list[str] = []
    for rel in files:
        target = root / rel
        if not target.exists():
            absent.append(rel)
            continue
        result = scan_file(target, repo_root=commands_in, allowed_urls=allowed_urls)
        result["path"] = rel
        results.append(result)
    total = sum(len(r["findings"]) for r in results)
    receipt = {
        "schema": "ont20.steering-scan/1",
        "filesScanned": [r["path"] for r in results],
        "absent": absent,
        "steeringDigests": {r["path"]: r["digest"] for r in results},
        "results": results,
        "findingCount": total,
        "clean": total == 0,
        "categoriesChecked": sorted(_CATEGORY_DOC),
        "sizeBoundBytes": MAX_STEERING_BYTES,
        "note": (
            "Steering files are executed by agents at cold start, often unread by a "
            "human. This scan treats them as untrusted input. A clean result means no "
            "known injection pattern was found; it does not certify intent."
        ),
    }
    receipt["scanDigest"] = digest_with("continuity.core.v2", receipt)
    return receipt
