"""Pattern detection (PD-01~05) — graph-structural checks, no LLM inference."""

from __future__ import annotations

from .models import CheckResult, CheckStatus
from .storage import GraphStore


def detect_patterns(store: GraphStore, node_id: str) -> list[CheckResult]:
    """Run pattern detection checks for a node in the graph context."""
    results = [
        _pd01_self_support(store, node_id),
        _pd02_unsupported_claim(store, node_id),
        _pd03_confirmation_bias(store, node_id),
        _pd04_dangling_references(store, node_id),
        _pd05_duplicate_links(store, node_id),
    ]
    return results


def _pd01_self_support(store: GraphStore, node_id: str) -> CheckResult:
    """Same agent linking supports to their own contribution."""
    node = store.get_node(node_id)
    if node is None:
        return CheckResult(id="PD-01", status=CheckStatus.PASS, reason="Node not found")

    incoming = store.get_incoming_links(node_id)
    for link in incoming:
        if link.relation == "supports" and link.agent_id == node.agent_id:
            source = store.get_node(link.source_id)
            if source and source.agent_id == node.agent_id:
                return CheckResult(
                    id="PD-01",
                    status=CheckStatus.FLAG,
                    reason=f"Self-support: agent '{node.agent_id}' supports own contribution via {link.source_id[:20]}...",
                )
    return CheckResult(id="PD-01", status=CheckStatus.PASS, reason="No self-support detected")


def _pd02_unsupported_claim(store: GraphStore, node_id: str) -> CheckResult:
    """Claim or hypothesis with zero evidence links."""
    node = store.get_node(node_id)
    if node is None or node.node_type not in ("claim", "hypothesis"):
        return CheckResult(id="PD-02", status=CheckStatus.PASS, reason="Not a claim/hypothesis")

    incoming = store.get_incoming_links(node_id)
    evidence_links = [l for l in incoming if l.relation in ("supports", "contradicts")]
    if not evidence_links:
        return CheckResult(
            id="PD-02",
            status=CheckStatus.FLAG,
            reason=f"{node.node_type} has no supporting or contradicting evidence",
        )
    return CheckResult(
        id="PD-02",
        status=CheckStatus.PASS,
        reason=f"{len(evidence_links)} evidence link(s) found",
    )


def _pd03_confirmation_bias(store: GraphStore, node_id: str) -> CheckResult:
    """All evidence links in the same direction (all supports or all contradicts)."""
    node = store.get_node(node_id)
    if node is None or node.node_type not in ("claim", "hypothesis"):
        return CheckResult(id="PD-03", status=CheckStatus.PASS, reason="Not a claim/hypothesis")

    incoming = store.get_incoming_links(node_id)
    evidence_links = [l for l in incoming if l.relation in ("supports", "contradicts")]
    if len(evidence_links) < 2:
        return CheckResult(id="PD-03", status=CheckStatus.PASS, reason="Too few evidence links")

    directions = {l.relation for l in evidence_links}
    if len(directions) == 1:
        return CheckResult(
            id="PD-03",
            status=CheckStatus.FLAG,
            reason=f"All {len(evidence_links)} evidence links are '{evidence_links[0].relation}' — possible confirmation bias",
        )
    return CheckResult(
        id="PD-03",
        status=CheckStatus.PASS,
        reason="Evidence includes both supporting and contradicting links",
    )


def _pd04_dangling_references(store: GraphStore, node_id: str) -> CheckResult:
    """Outgoing links pointing to non-existent nodes."""
    outgoing = store.get_outgoing_links(node_id)
    dangling = [l for l in outgoing if not store.node_exists(l.target_id)]
    if dangling:
        return CheckResult(
            id="PD-04",
            status=CheckStatus.BLOCK,
            reason=f"{len(dangling)} outgoing link(s) point to non-existent nodes",
        )
    return CheckResult(id="PD-04", status=CheckStatus.PASS, reason="All link targets exist")


def _pd05_duplicate_links(store: GraphStore, node_id: str) -> CheckResult:
    """Duplicate links between the same pair of nodes."""
    outgoing = store.get_outgoing_links(node_id)
    seen: set[tuple[str, str]] = set()
    duplicates = 0
    for link in outgoing:
        key = (link.target_id, link.relation)
        if key in seen:
            duplicates += 1
        seen.add(key)

    if duplicates > 0:
        return CheckResult(
            id="PD-05",
            status=CheckStatus.FLAG,
            reason=f"{duplicates} duplicate link(s) detected",
        )
    return CheckResult(id="PD-05", status=CheckStatus.PASS, reason="No duplicate links")
