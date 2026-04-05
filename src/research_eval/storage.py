"""SQLite-backed graph store for Contributions, Links, and Agents."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import (
    ContributionInput,
    LinkInput,
    StoredAgent,
    StoredLink,
    StoredNode,
    compute_link_hash,
    compute_node_hash,
    now_iso,
)

DEFAULT_DB_PATH = Path.home() / ".research-eval" / "graph.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    content_text TEXT,
    content_data JSON,
    created_at TEXT NOT NULL,
    trust_score REAL,
    acceptance TEXT
);

CREATE TABLE IF NOT EXISTS links (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES nodes(id),
    target_id TEXT NOT NULL REFERENCES nodes(id),
    relation TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    reputation REAL DEFAULT 0.3,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_id);
CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_id);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_nodes_agent ON nodes(agent_id);
"""


class GraphStore:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)

    def close(self) -> None:
        self.conn.close()

    # --- Nodes ---

    def insert_node(self, inp: ContributionInput) -> StoredNode:
        import json

        ts = now_iso()
        node_id = compute_node_hash(
            inp.content_text, inp.content_data, inp.contribution_type, inp.agent_id
        )
        content_data_json = (
            json.dumps(inp.content_data, ensure_ascii=False) if inp.content_data else None
        )
        self.conn.execute(
            "INSERT OR IGNORE INTO nodes (id, node_type, agent_id, content_text, content_data, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (node_id, inp.contribution_type, inp.agent_id, inp.content_text, content_data_json, ts),
        )
        self._ensure_agent(inp.agent_id)
        self.conn.commit()
        return StoredNode(
            id=node_id,
            node_type=inp.contribution_type,
            agent_id=inp.agent_id,
            content_text=inp.content_text,
            content_data=inp.content_data,
            created_at=ts,
        )

    def get_node(self, node_id: str) -> StoredNode | None:
        import json

        row = self.conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if row is None:
            return None
        return StoredNode(
            id=row["id"],
            node_type=row["node_type"],
            agent_id=row["agent_id"],
            content_text=row["content_text"],
            content_data=json.loads(row["content_data"]) if row["content_data"] else None,
            created_at=row["created_at"],
            trust_score=row["trust_score"],
            acceptance=row["acceptance"],
        )

    def node_exists(self, node_id: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM nodes WHERE id = ?", (node_id,)).fetchone()
        return row is not None

    def get_all_nodes(self) -> list[StoredNode]:
        import json

        rows = self.conn.execute("SELECT * FROM nodes").fetchall()
        return [
            StoredNode(
                id=r["id"],
                node_type=r["node_type"],
                agent_id=r["agent_id"],
                content_text=r["content_text"],
                content_data=json.loads(r["content_data"]) if r["content_data"] else None,
                created_at=r["created_at"],
                trust_score=r["trust_score"],
                acceptance=r["acceptance"],
            )
            for r in rows
        ]

    def update_node_trust(self, node_id: str, trust_score: float, acceptance: str) -> None:
        self.conn.execute(
            "UPDATE nodes SET trust_score = ?, acceptance = ? WHERE id = ?",
            (trust_score, acceptance, node_id),
        )
        self.conn.commit()

    def query_nodes(
        self,
        node_type: str | None = None,
        text_contains: str | None = None,
        min_trust: float | None = None,
    ) -> list[StoredNode]:
        import json

        clauses: list[str] = []
        params: list[object] = []
        if node_type:
            clauses.append("node_type = ?")
            params.append(node_type)
        if text_contains:
            clauses.append("content_text LIKE ?")
            params.append(f"%{text_contains}%")
        if min_trust is not None:
            clauses.append("trust_score >= ?")
            params.append(min_trust)
        where = " AND ".join(clauses) if clauses else "1=1"
        rows = self.conn.execute(f"SELECT * FROM nodes WHERE {where}", params).fetchall()
        return [
            StoredNode(
                id=r["id"],
                node_type=r["node_type"],
                agent_id=r["agent_id"],
                content_text=r["content_text"],
                content_data=json.loads(r["content_data"]) if r["content_data"] else None,
                created_at=r["created_at"],
                trust_score=r["trust_score"],
                acceptance=r["acceptance"],
            )
            for r in rows
        ]

    # --- Links ---

    def insert_link(self, inp: LinkInput) -> StoredLink:
        ts = now_iso()
        link_id = compute_link_hash(inp.source_id, inp.target_id, inp.relation, inp.agent_id, ts)
        self.conn.execute(
            "INSERT OR IGNORE INTO links (id, source_id, target_id, relation, agent_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (link_id, inp.source_id, inp.target_id, inp.relation, inp.agent_id, ts),
        )
        self._ensure_agent(inp.agent_id)
        self.conn.commit()
        return StoredLink(
            id=link_id,
            source_id=inp.source_id,
            target_id=inp.target_id,
            relation=inp.relation,
            agent_id=inp.agent_id,
            created_at=ts,
        )

    def get_incoming_links(self, node_id: str) -> list[StoredLink]:
        rows = self.conn.execute(
            "SELECT * FROM links WHERE target_id = ?", (node_id,)
        ).fetchall()
        return [
            StoredLink(
                id=r["id"],
                source_id=r["source_id"],
                target_id=r["target_id"],
                relation=r["relation"],
                agent_id=r["agent_id"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def get_outgoing_links(self, node_id: str) -> list[StoredLink]:
        rows = self.conn.execute(
            "SELECT * FROM links WHERE source_id = ?", (node_id,)
        ).fetchall()
        return [
            StoredLink(
                id=r["id"],
                source_id=r["source_id"],
                target_id=r["target_id"],
                relation=r["relation"],
                agent_id=r["agent_id"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def get_all_links(self) -> list[StoredLink]:
        rows = self.conn.execute("SELECT * FROM links").fetchall()
        return [
            StoredLink(
                id=r["id"],
                source_id=r["source_id"],
                target_id=r["target_id"],
                relation=r["relation"],
                agent_id=r["agent_id"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def count_connections(self, node_id: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) as c FROM links WHERE source_id = ? OR target_id = ?",
            (node_id, node_id),
        ).fetchone()
        return row["c"] if row else 0

    # --- Agents ---

    def _ensure_agent(self, agent_id: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO agents (id, reputation, created_at) VALUES (?, 0.3, ?)",
            (agent_id, now_iso()),
        )

    def get_agent(self, agent_id: str) -> StoredAgent | None:
        row = self.conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if row is None:
            return None
        return StoredAgent(id=row["id"], reputation=row["reputation"], created_at=row["created_at"])

    def get_all_agents(self) -> list[StoredAgent]:
        rows = self.conn.execute("SELECT * FROM agents").fetchall()
        return [
            StoredAgent(id=r["id"], reputation=r["reputation"], created_at=r["created_at"])
            for r in rows
        ]

    def update_agent_reputation(self, agent_id: str, reputation: float) -> None:
        self.conn.execute(
            "UPDATE agents SET reputation = ? WHERE id = ?", (reputation, agent_id)
        )
        self.conn.commit()
