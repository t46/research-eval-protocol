"""Human-facing dashboard for the Research Evaluation Protocol.

Read-only web UI that visualizes the knowledge graph, trust scores,
pattern detection results, and agent reputations.

Usage:
    uv run python -m dashboard.app
    # → http://localhost:8080
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure the src package is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from research_eval.storage import GraphStore, DEFAULT_DB_PATH
from research_eval.epirank import run_epirank
from research_eval.patterns import detect_patterns

app = FastAPI(title="Research Eval Dashboard", version="0.1.0")

STATIC_DIR = Path(__file__).parent / "static"

# DB path can be overridden via env var
DB_PATH = Path(os.environ.get("RESEARCH_EVAL_DB", str(DEFAULT_DB_PATH)))


def _get_store() -> GraphStore:
    return GraphStore(db_path=DB_PATH)


# --- API ---


@app.get("/api/stats")
def get_stats() -> dict:
    store = _get_store()
    try:
        nodes = store.get_all_nodes()
        links = store.get_all_links()
        agents = store.get_all_agents()

        type_counts: dict[str, int] = {}
        acceptance_counts: dict[str, int] = {}
        for n in nodes:
            type_counts[n.node_type] = type_counts.get(n.node_type, 0) + 1
            acc = n.acceptance or "unknown"
            acceptance_counts[acc] = acceptance_counts.get(acc, 0) + 1

        return {
            "node_count": len(nodes),
            "link_count": len(links),
            "agent_count": len(agents),
            "types": type_counts,
            "acceptance": acceptance_counts,
        }
    finally:
        store.close()


@app.get("/api/graph")
def get_graph() -> dict:
    """Return nodes + links in D3 force graph format."""
    store = _get_store()
    try:
        nodes = store.get_all_nodes()
        links = store.get_all_links()

        return {
            "nodes": [
                {
                    "id": n.id,
                    "type": n.node_type,
                    "agent_id": n.agent_id,
                    "content_text": n.content_text[:200],
                    "trust_score": n.trust_score,
                    "acceptance": n.acceptance,
                }
                for n in nodes
            ],
            "links": [
                {
                    "source": l.source_id,
                    "target": l.target_id,
                    "relation": l.relation,
                    "agent_id": l.agent_id,
                }
                for l in links
            ],
        }
    finally:
        store.close()


@app.get("/api/nodes")
def get_nodes(
    node_type: str | None = Query(None),
    text_contains: str | None = Query(None),
    min_trust: float | None = Query(None),
) -> dict:
    store = _get_store()
    try:
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
                for n in nodes
            ],
        }
    finally:
        store.close()


@app.get("/api/nodes/{node_id:path}")
def get_node_detail(node_id: str) -> dict:
    store = _get_store()
    try:
        node = store.get_node(node_id)
        if node is None:
            return JSONResponse({"error": "Node not found"}, status_code=404)

        patterns = detect_patterns(store, node_id)
        incoming = store.get_incoming_links(node_id)
        outgoing = store.get_outgoing_links(node_id)

        return {
            "id": node.id,
            "type": node.node_type,
            "agent_id": node.agent_id,
            "content_text": node.content_text,
            "content_data": node.content_data,
            "trust_score": node.trust_score,
            "acceptance": node.acceptance,
            "created_at": node.created_at,
            "patterns": [
                {"id": p.id, "status": p.status.value, "reason": p.reason}
                for p in patterns
            ],
            "incoming_links": [
                {"source_id": l.source_id, "relation": l.relation, "agent_id": l.agent_id}
                for l in incoming
            ],
            "outgoing_links": [
                {"target_id": l.target_id, "relation": l.relation, "agent_id": l.agent_id}
                for l in outgoing
            ],
        }
    finally:
        store.close()


@app.get("/api/agents")
def get_agents() -> dict:
    store = _get_store()
    try:
        agents = store.get_all_agents()
        nodes = store.get_all_nodes()

        # Count nodes per agent
        agent_node_counts: dict[str, int] = {}
        for n in nodes:
            agent_node_counts[n.agent_id] = agent_node_counts.get(n.agent_id, 0) + 1

        return {
            "agents": [
                {
                    "id": a.id,
                    "reputation": round(a.reputation, 4),
                    "node_count": agent_node_counts.get(a.id, 0),
                    "created_at": a.created_at,
                }
                for a in agents
            ]
        }
    finally:
        store.close()


@app.post("/api/recompute")
def recompute_trust() -> dict:
    """Re-run EpiRank on the full graph."""
    store = _get_store()
    try:
        trust_scores = run_epirank(store)
        return {
            "recomputed": True,
            "node_count": len(trust_scores),
        }
    finally:
        store.close()


# --- Static files ---

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


if __name__ == "__main__":
    print(f"Reading from DB: {DB_PATH}")
    print("Dashboard: http://localhost:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080)
