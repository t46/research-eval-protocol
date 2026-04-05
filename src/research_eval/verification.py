"""Structural verification engine — integrity checks (IC-01~05) with no LLM inference."""

from __future__ import annotations

import re

from .models import (
    CheckResult,
    CheckStatus,
    ContributionInput,
    ContributionType,
    StructuralVerification,
)

# Evaluative language patterns for IC-05 (observation should be theory-neutral)
_EVALUATIVE_PATTERNS = re.compile(
    r"\b(significant|important|clearly|obviously|proves|confirms|demonstrates|remarkable"
    r"|groundbreaking|novel|superior|inferior|best|worst|trivial)\b",
    re.IGNORECASE,
)

# Valid core types
_CORE_TYPES = {t.value for t in ContributionType}

# Type-specific required fields in content_data (IC-04)
_REQUIRED_FIELDS: dict[str, list[str]] = {
    "claim": ["assertion"],
    "hypothesis": ["prediction"],
    "evidence": ["direction"],
    "method": ["procedure"],
}


def verify(inp: ContributionInput) -> StructuralVerification:
    """Run all integrity checks on a ContributionInput and return results."""
    checks = [
        _ic01_content_nonempty(inp),
        _ic02_valid_type(inp),
        _ic03_agent_nonempty(inp),
        _ic04_type_specific_fields(inp),
        _ic05_observation_evaluative(inp),
    ]
    overall = _compute_overall(checks)
    return StructuralVerification(checks=checks, overall=overall)


def _compute_overall(checks: list[CheckResult]) -> CheckStatus:
    if any(c.status == CheckStatus.BLOCK for c in checks):
        return CheckStatus.BLOCK
    if any(c.status == CheckStatus.FLAG for c in checks):
        return CheckStatus.FLAG
    return CheckStatus.PASS


def _ic01_content_nonempty(inp: ContributionInput) -> CheckResult:
    text = inp.content_text.strip()
    if not text:
        return CheckResult(id="IC-01", status=CheckStatus.BLOCK, reason="content_text is empty")
    if len(text) < 20:
        return CheckResult(
            id="IC-01",
            status=CheckStatus.BLOCK,
            reason=f"content_text too short ({len(text)} chars, minimum 20)",
        )
    return CheckResult(id="IC-01", status=CheckStatus.PASS, reason="content_text is sufficient")


def _ic02_valid_type(inp: ContributionInput) -> CheckResult:
    t = inp.contribution_type
    if t in _CORE_TYPES:
        return CheckResult(id="IC-02", status=CheckStatus.PASS, reason=f"Valid core type: {t}")
    if t.startswith("custom:"):
        return CheckResult(
            id="IC-02", status=CheckStatus.FLAG, reason=f"Custom type: {t} (not in core registry)"
        )
    return CheckResult(
        id="IC-02",
        status=CheckStatus.BLOCK,
        reason=f"Invalid type: {t} (not in core registry and missing custom: prefix)",
    )


def _ic03_agent_nonempty(inp: ContributionInput) -> CheckResult:
    if not inp.agent_id.strip():
        return CheckResult(id="IC-03", status=CheckStatus.BLOCK, reason="agent_id is empty")
    return CheckResult(id="IC-03", status=CheckStatus.PASS, reason="agent_id is present")


def _ic04_type_specific_fields(inp: ContributionInput) -> CheckResult:
    required = _REQUIRED_FIELDS.get(inp.contribution_type)
    if required is None:
        return CheckResult(
            id="IC-04", status=CheckStatus.PASS, reason="No type-specific field requirements"
        )
    if inp.content_data is None:
        return CheckResult(
            id="IC-04",
            status=CheckStatus.FLAG,
            reason=f"content_data is null but type '{inp.contribution_type}' recommends: {required}",
        )
    missing = [f for f in required if f not in inp.content_data]
    if missing:
        return CheckResult(
            id="IC-04",
            status=CheckStatus.FLAG,
            reason=f"content_data missing recommended fields: {missing}",
        )
    return CheckResult(
        id="IC-04", status=CheckStatus.PASS, reason="Type-specific fields present"
    )


def _ic05_observation_evaluative(inp: ContributionInput) -> CheckResult:
    if inp.contribution_type != "observation":
        return CheckResult(
            id="IC-05", status=CheckStatus.PASS, reason="Not an observation, check skipped"
        )
    matches = _EVALUATIVE_PATTERNS.findall(inp.content_text)
    if matches:
        return CheckResult(
            id="IC-05",
            status=CheckStatus.FLAG,
            reason=f"Observation contains evaluative language: {matches[:5]}",
        )
    return CheckResult(
        id="IC-05", status=CheckStatus.PASS, reason="Observation is descriptive"
    )
