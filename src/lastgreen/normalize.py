"""Reduce a log line to a template so the same line from two runs compares equal."""

from __future__ import annotations

import re

_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:[.,]\d+)?(?:Z|[+-]\d\d:?\d\d)?"), "<time>"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "<id>"),
    (re.compile(r"\b0x[0-9a-f]+\b", re.I), "<addr>"),
    (re.compile(r"\b(?=[0-9a-f]*[a-f])(?=[0-9a-f]*\d)[0-9a-f]{7,}\b"), "<hex>"),
    # Random names from Python's tempfile and mktemp.
    (re.compile(r"\btmp[a-z0-9_]{6,}\b"), "<tmp>"),
    (re.compile(r"\d+"), "#"),
    (re.compile(r"\s+"), " "),
]


def normalize(line: str) -> str:
    for pattern, replacement in _RULES:
        line = pattern.sub(replacement, line)
    return line.strip()
