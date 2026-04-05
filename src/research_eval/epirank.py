"""EpiRank — minimal trust propagation algorithm for the research knowledge graph.

Based on the full design in trust-reputation-algorithm.md.
Minimal version: C(n) + R(a) without independence bonus, calibration, or Sybil detection.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from .models import (
    POLARITY,
    TYPE_PRIOR,
    AcceptanceStatus,
    ContributionType,
    LinkRelation,
    StoredLink,
    StoredNode,
)
from .storage import GraphStore

# --- Parameters (from design doc recommendations) ---

ALPHA = 3.0  # sigmoid steepness
BETA = 0.85  # damping factor (same as PageRank)
T_HALF_DAYS = 365  # temporal decay half-life
LAMBDA = math.log(2)
R_SEED = 0.3  # cold start reputation
MAX_ITER = 100
EPSILON = 1e-6

# Acceptance thresholds
ACCEPT_THRESHOLD = 0.7
REJECT_THRESHOLD = 0.3


def sigmoid(x: float) -> float:
    """Sigmoid mapping to [0, 1]."""
    return 1.0 / (1.0 + math.exp(-x))


def temporal_decay(created_at: str, now: datetime | None = None) -> float:
    """Exponential decay with half-life T_HALF_DAYS."""
    if now is None:
        now = datetime.now(timezone.utc)
    try:
        t = datetime.fromisoformat(created_at)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return 0.5  # fallback for unparseable timestamps
    delta_days = (now - t).total_seconds() / 86400
    if delta_days < 0:
        delta_days = 0
    return math.exp(-LAMBDA * delta_days / T_HALF_DAYS)


def get_polarity(relation: str) -> float:
    """Get polarity for a relation type. Unknown relations return 0.0."""
    try:
        return POLARITY[LinkRelation(relation)]
    except (ValueError, KeyError):
        return 0.0


def get_type_prior(node_type: str) -> float:
    """Get type-based prior trust for isolated nodes."""
    try:
        return TYPE_PRIOR[ContributionType(node_type)]
    except (ValueError, KeyError):
        return 0.5  # neutral prior for custom types


def compute_acceptance(trust: float, node_id: str, all_links: list[StoredLink], node_trusts: dict[str, float]) -> AcceptanceStatus:
    """Determine acceptance status based on trust score and contradicting nodes."""
    if trust < REJECT_THRESHOLD:
        return AcceptanceStatus.REJECTED
    if trust < ACCEPT_THRESHOLD:
        return AcceptanceStatus.UNCERTAIN

    # Check for high-trust contradictions
    for link in all_links:
        if link.target_id == node_id and link.relation == "contradicts":
            source_trust = node_trusts.get(link.source_id, 0.5)
            if source_trust >= ACCEPT_THRESHOLD:
                return AcceptanceStatus.CONTESTED
        if link.source_id == node_id and link.relation == "contradicts":
            target_trust = node_trusts.get(link.target_id, 0.5)
            if target_trust >= ACCEPT_THRESHOLD:
                return AcceptanceStatus.CONTESTED

    return AcceptanceStatus.ACCEPTED


def run_epirank(store: GraphStore) -> dict[str, float]:
    """Run EpiRank on the entire graph. Returns {node_id: trust_score}.

    Also updates node trust scores, acceptance status, and agent reputations in the store.
    """
    nodes = store.get_all_nodes()
    links = store.get_all_links()
    agents = store.get_all_agents()

    if not nodes:
        return {}

    # Initialize
    C: dict[str, float] = {n.id: 0.5 for n in nodes}
    R: dict[str, float] = {a.id: a.reputation for a in agents}

    # Build index: node_id -> agent_id
    node_agent: dict[str, str] = {n.id: n.agent_id for n in nodes}
    node_type: dict[str, str] = {n.id: n.node_type for n in nodes}

    # Build index: node_id -> incoming links
    incoming: dict[str, list[StoredLink]] = {n.id: [] for n in nodes}
    for link in links:
        if link.target_id in incoming:
            incoming[link.target_id].append(link)

    now = datetime.now(timezone.utc)

    for iteration in range(MAX_ITER):
        C_new: dict[str, float] = {}

        for node in nodes:
            in_links = incoming[node.id]

            if not in_links:
                # No incoming links — use type-based prior
                C_new[node.id] = BETA * get_type_prior(node.node_type) + (1 - BETA) * 0.5
                continue

            pos_sum = 0.0
            neg_sum = 0.0
            total_weight = 0.0

            for link in in_links:
                p = get_polarity(link.relation)
                if p == 0.0:
                    continue

                d = temporal_decay(link.created_at, now)
                source_agent = node_agent.get(link.source_id, link.agent_id)
                r = R.get(source_agent, R_SEED)
                source_trust = C.get(link.source_id, 0.5)

                w = abs(p) * d * r * source_trust
                total_weight += w

                if p > 0:
                    pos_sum += p * d * r * source_trust
                else:
                    neg_sum += abs(p) * d * r * source_trust

            if total_weight > 0:
                raw = (pos_sum - neg_sum) / total_weight
                computed = sigmoid(ALPHA * raw)
            else:
                computed = get_type_prior(node.node_type)

            # Damping: mix with base prior
            C_new[node.id] = BETA * computed + (1 - BETA) * 0.5

        # Update agent reputations: R(a) = weighted mean of authored nodes' trust
        for agent in agents:
            authored = [n for n in nodes if n.agent_id == agent.id]
            if not authored:
                continue
            weights = [temporal_decay(n.created_at, now) for n in authored]
            total_w = sum(weights)
            if total_w > 0:
                track = sum(
                    C_new.get(n.id, 0.5) * w for n, w in zip(authored, weights)
                ) / total_w
            else:
                track = 0.5
            R[agent.id] = max(0.05, min(1.0, track))

        # Check convergence
        max_delta = max(abs(C_new[n.id] - C[n.id]) for n in nodes)
        C = C_new
        if max_delta < EPSILON:
            break

    # Write results to store
    for node in nodes:
        trust = C[node.id]
        acceptance = compute_acceptance(trust, node.id, links, C)
        store.update_node_trust(node.id, trust, acceptance.value)

    for agent in agents:
        store.update_agent_reputation(agent.id, R.get(agent.id, R_SEED))

    return C
