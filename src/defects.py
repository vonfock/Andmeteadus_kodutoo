"""Shared helpers for parsing inspection defect strings."""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

VALID_SEVERITIES = {"VO", "OV", "EOV"}
_DELIMITER_RE = re.compile(r"[;,\r\n]+")


def split_rikked_entries(value: object) -> list[str]:
    """Split RIKKED into non-empty raw entries."""
    if not isinstance(value, str) or not value.strip():
        return []
    return [part.strip() for part in _DELIMITER_RE.split(value) if part.strip()]


def parse_rikked(value: object) -> list[tuple[str, int]]:
    """Parse RIKKED into ``(severity, defect_id)`` pairs.

    The source data uses semicolons in observed yearly CSVs, while older
    project code also expected commas. Accept both delimiters to keep batch
    processing and dashboard queries aligned.
    """
    defects: list[tuple[str, int]] = []
    for part in split_rikked_entries(value):
        if ":" not in part:
            continue

        severity, defect_id = part.split(":", 1)
        severity = severity.strip().upper()
        defect_id = defect_id.strip()

        if severity not in VALID_SEVERITIES:
            continue

        try:
            defects.append((severity, int(defect_id)))
        except ValueError:
            continue

    return defects


def count_severities(defects: Iterable[tuple[str, int]]) -> Counter[str]:
    """Count parsed defects by severity."""
    return Counter(severity for severity, _ in defects)


def defect_ids(defects: Iterable[tuple[str, int]]) -> list[int]:
    """Return defect IDs from parsed defects."""
    return [defect_id for _, defect_id in defects]
