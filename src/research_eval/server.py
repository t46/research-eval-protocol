"""MCP Server for the Research Evaluation Protocol.

Exposes 5 tools and 5 resources for AI research agent evaluation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .epirank import run_epirank
from .models import (
    CheckStatus,
    ContributionInput,
    EvaluationEnvelope,
    LinkInput,
    MetaDimensions,
    ReproducibilityStatus,
    TrustScores,
    AcceptanceStatus,
)
from .patterns import detect_patterns
from .storage import GraphStore
from .verification import verify

# --- Server setup ---

mcp = FastMCP(
    "research-eval-protocol",
    version="0.1.0",
    description="Open protocol for evaluating AI research agent outputs. "
    "Provides structural verification, trust propagation (EpiRank), and pattern detection.",
)

_store: GraphStore | None = None


def _get_store() -> GraphStore:
    global _store
    if _store is None:
        _store = GraphStore()
    return _store


# --- Skills & spec file paths ---

_SPEC_DIR = Path(__file__).parent.parent.parent / "spec"
_SKILLS_DIR = _SPEC_DIR / "skills"


def _read_file(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"File not found: {path}"


# --- Resources ---


@mcp.resource("protocol://spec/v0.1")
def get_protocol_spec() -> str:
    """Protocol specification overview."""
    return _read_file(_SPEC_DIR / "v0.1" / "protocol.md")


@mcp.resource("protocol://types")
def get_types() -> str:
    """Core Contribution types in v0.1."""
    return """# Contribution Types (v0.1)

| Type | Description |
|------|------------|
| claim | Verifiable factual assertion |
| hypothesis | Unverified predictive assertion |
| evidence | Data or argument supporting/refuting another Contribution |
| method | Reusable procedure or technique |
| critique | Identification of problems in existing Contributions |
| observation | Raw, theory-neutral recording |

Custom types: use `custom:your-type-name` prefix."""


@mcp.resource("protocol://relations")
def get_relations() -> str:
    """Core Link relations in v0.1."""
    return """# Link Relations (v0.1)

| Relation | Polarity | Description |
|----------|----------|------------|
| supports | +1.0 | A increases justification of B |
| contradicts | -1.0 | A decreases justification of B |
| extends | +0.7 | A develops/refines B |
| derives-from | +0.5 | A logically follows from B |

Custom relations: use `custom:your-relation` prefix."""


@mcp.resource("protocol://skills/contribution-format")
def get_skill_contribution_format() -> str:
    """Skill: How to format research outputs as Contributions."""
    return _read_file(_SKILLS_DIR / "research-contribution-format.md")


@mcp.resource("protocol://skills/evaluation-interpret")
def get_skill_evaluation_interpret() -> str:
    """Skill: How to interpret Evaluation Envelopes."""
    return _read_file(_SKILLS_DIR / "research-evaluation-interpret.md")


# --- Tools ---


@mcp.tool()
def verify_contribution(
    content_text: str,
    contribution_type: str,
    agent_id: str,
    content_data: dict[str, Any] | None = None,
) -> dict:
    """Verify a Contribution's structural integrity without registering it in the graph.

    Returns an EvaluationEnvelope with structural checks (PASS/FLAG/BLOCK).
    Use this to check a contribution before submitting it.

    Args:
        content_text: Main textual content (min 20 chars)
        contribution_type: Type from registry (claim, hypothesis, evidence, method, critique, observation) or custom:* prefix
        agent_id: Identity of the authoring agent
        content_data: Optional structured data with type-specific fields
    """
    inp = ContributionInput(
        content_text=content_text,
        content_data=content_data,
        contribution_type=contribution_type,
        agent_id=agent_id,
    )
    structural = verify(inp)
    envelope = EvaluationEnvelope(structural=structural)
    return envelope.model_dump()


@mcp.tool()
def submit_contribution(
    content_text: str,
    contribution_type: str,
    agent_id: str,
    content_data: dict[str, Any] | None = None,
) -> dict:
    """Verify and register a Contribution in the knowledge graph.

    If structural verification results in BLOCK, the contribution is rejected.
    Returns the EvaluationEnvelope plus the node_id if registered.

    Args:
        content_text: Main textual content (min 20 chars)
        contribution_type: Type from registry (claim, hypothesis, evidence, method, critique, observation) or custom:* prefix
        agent_id: Identity of the authoring agent
        content_data: Optional structured data with type-specific fields
    """
    store = _get_store()
    inp = ContributionInput(
        content_text=content_text,
        content_data=content_data,
        contribution_type=contribution_type,
        agent_id=agent_id,
    )
    structural = verify(inp)

    if structural.overall == CheckStatus.BLOCK:
        envelope = EvaluationEnvelope(structural=structural)
        return {"envelope": envelope.model_dump(), "node_id": None, "registered": False}

    node = store.insert_node(inp)

    # Compute meta dimensions
    connectivity = store.count_connections(node.id)
    meta = MetaDimensions(
        connectivity=connectivity,
        reproducibility_status=ReproducibilityStatus.UNTESTED,
    )

    # Run EpiRank to get trust scores
    trust_scores = run_epirank(store)
    trust = trust_scores.get(node.id, 0.5)
    agent = store.get_agent(agent_id)
    rep = agent.reputation if agent else 0.3

    # Determine acceptance
    from .epirank import compute_acceptance
    all_links = store.get_all_links()
    acceptance = compute_acceptance(trust, node.id, all_links, trust_scores)

    trust_result = TrustScores(
        claim_trust=round(trust, 4),
        agent_reputation=round(rep, 4),
        acceptance=acceptance,
    )

    envelope = EvaluationEnvelope(structural=structural, trust=trust_result, meta=meta)
    return {"envelope": envelope.model_dump(), "node_id": node.id, "registered": True}


@mcp.tool()
def submit_link(
    source_id: str,
    target_id: str,
    relation: str,
    agent_id: str,
) -> dict:
    """Register a Link between two Contributions in the knowledge graph.

    Both source and target must already exist in the graph.

    Args:
        source_id: Content-hash ID of the source Contribution (sha256:...)
        target_id: Content-hash ID of the target Contribution (sha256:...)
        relation: Relation type (supports, contradicts, derives-from, extends) or custom:*
        agent_id: Identity of the agent creating this link
    """
    store = _get_store()

    if not store.node_exists(source_id):
        return {"error": f"Source node not found: {source_id}", "registered": False}
    if not store.node_exists(target_id):
        return {"error": f"Target node not found: {target_id}", "registered": False}

    inp = LinkInput(
        source_id=source_id,
        target_id=target_id,
        relation=relation,
        agent_id=agent_id,
    )
    link = store.insert_link(inp)
    return {"link_id": link.id, "registered": True}


@mcp.tool()
def compute_trust(node_id: str) -> dict:
    """Compute trust scores for a specific node using EpiRank.

    Runs the full EpiRank algorithm on the graph and returns the result for the specified node.
    Also returns pattern detection results (PD-01~05).

    Args:
        node_id: Content-hash ID of the node (sha256:...)
    """
    store = _get_store()
    node = store.get_node(node_id)
    if node is None:
        return {"error": f"Node not found: {node_id}"}

    # Run EpiRank
    trust_scores = run_epirank(store)
    trust = trust_scores.get(node_id, 0.5)

    # Get updated agent reputation
    agent = store.get_agent(node.agent_id)
    rep = agent.reputation if agent else 0.3

    # Acceptance status
    from .epirank import compute_acceptance
    all_links = store.get_all_links()
    acceptance = compute_acceptance(trust, node_id, all_links, trust_scores)

    # Pattern detection
    patterns = detect_patterns(store, node_id)

    # Meta dimensions
    connectivity = store.count_connections(node_id)

    return {
        "node_id": node_id,
        "trust": {
            "claim_trust": round(trust, 4),
            "agent_reputation": round(rep, 4),
            "acceptance": acceptance.value,
        },
        "meta": {
            "connectivity": connectivity,
            "reproducibility_status": "untested",
        },
        "patterns": [p.model_dump() for p in patterns],
    }


@mcp.tool()
def query_network(
    node_type: str | None = None,
    text_contains: str | None = None,
    min_trust: float | None = None,
) -> dict:
    """Query the knowledge graph for Contributions matching criteria.

    Args:
        node_type: Filter by contribution type (claim, hypothesis, evidence, method, critique, observation)
        text_contains: Filter by text content (substring match)
        min_trust: Filter by minimum trust score (0.0-1.0)
    """
    store = _get_store()
    nodes = store.query_nodes(
        node_type=node_type,
        text_contains=text_contains,
        min_trust=min_trust,
    )
    return {
        "count": len(nodes),
        "nodes": [
            {
                "id": n.id,
                "type": n.node_type,
                "agent_id": n.agent_id,
                "content_text": n.content_text[:200],
                "trust_score": n.trust_score,
                "acceptance": n.acceptance,
            }
            for n in nodes[:50]  # limit to 50 results
        ],
    }
