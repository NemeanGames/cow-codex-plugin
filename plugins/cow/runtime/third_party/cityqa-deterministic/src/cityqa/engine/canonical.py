"""Deterministic canonicalization (IMPLEMENTATION DIRECTIVE section 11).

Two representations exist for every receipt and every artifact:

    RAW           immutable original bytes plus ``rawDigest``
    CANONICAL     a semantic projection plus ``semanticDigest``

This module produces the canonical projection only. It never rewrites the raw
bytes; callers that need the original must read the raw record. Which fields
leave the semantic projection is decided by the canonicalization policy
instance, not by this code -- an exclusion the policy has not declared is an
error, not a silent drop.
"""

from __future__ import annotations

import math
import re
import unicodedata
from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "CanonicalizationError",
    "canonical_bytes",
    "canonical_text",
    "canonical_path",
    "project",
    "stable_sort_key",
    "normalize_number",
    "excluded_paths_for",
]

# Compact JSON separators required by the directive.
_ITEM_SEP = ","
_KEY_SEP = ":"

_BACKSLASH = re.compile(r"\\+")
_MULTI_SLASH = re.compile(r"/{2,}")

_MAX_DEPTH = 128


class CanonicalizationError(ValueError):
    """Raised when a value cannot be canonicalized deterministically."""


def canonical_path(raw: str) -> str:
    """Return the forward-slash logical form of ``raw``.

    Windows separators collapse to ``/``, duplicate separators collapse, and a
    drive letter is upper-cased so that ``z:/x`` and ``Z:/x`` share an identity.
    The raw path is not discarded by this function -- raw receipts retain it.
    """
    if not isinstance(raw, str):
        raise CanonicalizationError("path must be str, got " + type(raw).__name__)
    text = _BACKSLASH.sub("/", raw)
    text = _MULTI_SLASH.sub("/", text)
    if len(text) >= 2 and text[1] == ":" and text[0].isalpha():
        text = text[0].upper() + text[1:]
    if len(text) > 1 and text.endswith("/"):
        text = text.rstrip("/") or "/"
    return unicodedata.normalize("NFC", text)


def normalize_number(value: Any) -> Any:
    """Reject values that have no canonical numeric representation."""
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise CanonicalizationError("non-finite Decimal in canonical value")
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise CanonicalizationError("non-finite float in canonical value")
        return value
    return value


def _key_text(key: Any) -> str:
    if not isinstance(key, str):
        raise CanonicalizationError(
            "object keys must be str for canonical ordering, got " + type(key).__name__
        )
    return unicodedata.normalize("NFC", key)


def _decimal_text(value: Decimal) -> str:
    """Exact decimal text, normalized so 1.10 and 1.1 share one identity."""
    text = format(value.normalize(), "f")
    if text in ("-0", "-0.0"):
        return "0"
    return text


def _float_text(value: float) -> str:
    if value == int(value) and abs(value) < 1e16:
        return str(int(value))
    return repr(value)


_ESCAPES = {
    0x22: "\\\"",
    0x5C: "\\\\",
    0x08: "\\b",
    0x0C: "\\f",
    0x0A: "\\n",
    0x0D: "\\r",
    0x09: "\\t",
}


def _string_text(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    parts = ["\""]
    for char in value:
        code = ord(char)
        escape = _ESCAPES.get(code)
        if escape is not None:
            parts.append(escape)
        elif code < 0x20 or code == 0x7F:
            parts.append("\\u%04x" % code)
        else:
            parts.append(char)
    parts.append("\"")
    return "".join(parts)


def _emit(value: Any, out: list[str], depth: int = 0) -> None:
    """Append the canonical JSON text of ``value`` to ``out``."""
    if depth > _MAX_DEPTH:
        raise CanonicalizationError("canonical projection exceeded maximum nesting depth")

    value = normalize_number(value)

    if value is None:
        out.append("null")
        return
    if value is True:
        out.append("true")
        return
    if value is False:
        out.append("false")
        return
    if isinstance(value, Decimal):
        out.append(_decimal_text(value))
        return
    if isinstance(value, int):
        out.append(str(value))
        return
    if isinstance(value, float):
        out.append(_float_text(value))
        return
    if isinstance(value, str):
        out.append(_string_text(value))
        return
    if isinstance(value, Mapping):
        items = sorted(value.items(), key=lambda kv: _key_text(kv[0]))
        out.append("{")
        for index, pair in enumerate(items):
            if index:
                out.append(_ITEM_SEP)
            out.append(_string_text(_key_text(pair[0])))
            out.append(_KEY_SEP)
            _emit(pair[1], out, depth + 1)
        out.append("}")
        return
    if isinstance(value, (set, frozenset)):
        raise CanonicalizationError(
            "set encountered in canonical projection; sort it into a list with "
            "stable_sort_key so the ordering is explicit"
        )
    if isinstance(value, (list, tuple)):
        # Sequence order is semantic and is preserved exactly as given.
        out.append("[")
        for index, sub in enumerate(value):
            if index:
                out.append(_ITEM_SEP)
            _emit(sub, out, depth + 1)
        out.append("]")
        return
    raise CanonicalizationError(
        "value of type " + type(value).__name__ + " has no canonical representation"
    )


def canonical_text(value: Any) -> str:
    """Return the canonical JSON text of ``value`` without a trailing newline."""
    out: list[str] = []
    _emit(value, out)
    return "".join(out)


def canonical_bytes(value: Any) -> bytes:
    """Return canonical UTF-8 bytes: no BOM, sorted keys, one terminal newline."""
    return (canonical_text(value) + "\n").encode("utf-8")


def stable_sort_key(item: Any) -> tuple[int, str]:
    """Total order used for nonsemantic sets.

    The type rank keeps heterogeneous collections orderable without raising;
    the canonical text of the item breaks ties deterministically.
    """
    rank = {
        type(None): 0,
        bool: 1,
        int: 2,
        float: 2,
        Decimal: 2,
        str: 3,
        list: 4,
        tuple: 4,
        dict: 5,
    }.get(type(item), 6)
    return (rank, canonical_text(item))


class _Omit:
    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "<OMIT>"


_OMIT = _Omit()


def _project(value: Any, excluded: frozenset[str], path: str) -> Any:
    if path in excluded:
        return _OMIT
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key in sorted(value.keys(), key=_key_text):
            child = _project(value[key], excluded, path + "." + str(key))
            if child is not _OMIT:
                result[key] = child
        return result
    if isinstance(value, (list, tuple)) and not isinstance(value, (str, bytes)):
        items = []
        for element in value:
            child = _project(element, excluded, path + "[]")
            if child is not _OMIT:
                items.append(child)
        return items
    return value


def project(value: Any, excluded_paths: Iterable[str] = (), path: str = "$") -> Any:
    """Return ``value`` with policy-declared exclusions removed.

    ``excluded_paths`` uses a restricted JSONPath dialect: ``$.a.b`` addresses a
    field, and ``$.a[].b`` addresses that field inside every element of the
    array at ``$.a``. Only exclusions the canonicalization policy declares reach
    this function; enforcing that is the caller's responsibility.
    """
    return _project(value, frozenset(excluded_paths), path)


def excluded_paths_for(policy: Mapping[str, Any], receipt_type: str) -> tuple[str, ...]:
    """Return the exclusion list a canonicalization policy declares for a type.

    An undeclared receipt type yields the policy default. Nothing is dropped
    that the policy has not named.
    """
    by_type = policy.get("exclusionsByReceiptType", {})
    declared: Sequence[str] = by_type.get(receipt_type, policy.get("defaultExclusions", []))
    return tuple(sorted(str(item) for item in declared))
