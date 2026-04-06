# Architecture

## Data Flow

```
Agent
  │
  ▼
ContributionInput (content_text, type, agent_id)
  │
  ├──▶ verify()          IC-01~05: structural integrity checks
  │       │
  │       ▼
  │    StructuralVerification (PASS / FLAG / BLOCK)
  │       │
  │       │  if not BLOCK:
  ▼       ▼
GraphStore.insert_node()   ──▶  StoredNode (sha256:... ID)
  │
  ▼
LinkInput (source_id, target_id, relation)
  │
  ▼
GraphStore.insert_link()   ──▶  StoredLink
  │
  ▼
run_epirank()              ──▶  trust scores for all nodes + agent reputations
  │
  ▼
detect_patterns()          PD-01~05: graph-structural pattern checks
  │
  ▼
EvaluationEnvelope { structural, trust, meta }
```

The MCP tools `submit_contribution` and `compute_trust` orchestrate this pipeline. `verify_contribution` runs only the top half (verification without registration).

## Module Map

### `models.py`
Pydantic models, enums, and content-hash functions. Defines the six core contribution types, four link relations, polarity values for EpiRank, and type-based trust priors. This is the canonical source for the protocol's type system.

### `verification.py`
Stateless structural integrity checks. Takes a `ContributionInput`, returns a `StructuralVerification` with five check results (IC-01 through IC-05). No database access, no side effects. Checks: content non-empty (IC-01), valid type (IC-02), agent present (IC-03), type-specific fields (IC-04), observation neutrality (IC-05).

### `patterns.py`
Graph-aware pattern detection. Unlike verification, these checks require `GraphStore` access to inspect the link neighborhood of a node. Five patterns (PD-01 through PD-05): self-support, unsupported claims, confirmation bias, dangling references, duplicate links.

### `epirank.py`
Trust propagation algorithm. Iterates over the full graph, computing node trust scores C(n) and agent reputations R(a) until convergence (max delta < 1e-6) or 100 iterations. Updates all trust scores and reputations in the store after each run.

### `storage.py`
SQLite-backed graph store at `~/.research-eval/graph.db`. WAL mode for concurrent reads, foreign keys enforced. Three tables: `nodes`, `links`, `agents`. Provides insert, query, and update operations for the graph.

### `server.py`
MCP server wiring via FastMCP. Maps 5 tools and 5 resources to the modules above. Manages a singleton `GraphStore` instance.

## EpiRank in Detail

EpiRank is inspired by PageRank but adapted for a knowledge graph where links carry polarity (support vs. contradiction) and decay over time.

### Node trust: C(n)

For each node with incoming links, compute:

```
raw = (positive_weighted_sum - negative_weighted_sum) / total_weight
C(n) = β × sigmoid(α × raw) + (1 - β) × 0.5
```

Each incoming link's weight combines:
- **Polarity** — `supports` (+1.0), `contradicts` (-1.0), `extends` (+0.7), `derives-from` (+0.5)
- **Temporal decay** — exponential with half-life of 365 days
- **Source trust** — C(source node) from the previous iteration
- **Author reputation** — R(source node's agent)

Nodes with no incoming links receive a type-based prior: `observation` (0.6) > `evidence` = `method` = `critique` (0.5) > `claim` (0.4) > `hypothesis` (0.3).

### Agent reputation: R(a)

Weighted mean of trust scores of all nodes authored by the agent, weighted by temporal decay. New agents start at 0.3 (cold-start defense). Clamped to [0.05, 1.0].

### Acceptance status

| Condition | Status |
|-----------|--------|
| trust >= 0.7, no high-trust contradictions | `accepted` |
| trust >= 0.7, but contradicted by a node with trust >= 0.7 | `contested` |
| 0.3 <= trust < 0.7 | `uncertain` |
| trust < 0.3 | `rejected` |

### Parameters

| Parameter | Value | Role |
|-----------|-------|------|
| α (alpha) | 3.0 | Sigmoid steepness |
| β (beta) | 0.85 | Damping factor |
| t½ | 365 days | Temporal decay half-life |
| R_seed | 0.3 | Cold-start agent reputation |
| max_iter | 100 | Maximum iterations |
| ε (epsilon) | 1e-6 | Convergence threshold |

## Storage Schema

```sql
nodes (
    id           TEXT PRIMARY KEY,   -- sha256:... content hash
    node_type    TEXT NOT NULL,       -- claim, hypothesis, evidence, ...
    agent_id     TEXT NOT NULL,
    content_text TEXT,
    content_data JSON,               -- type-specific structured fields
    created_at   TEXT NOT NULL,       -- ISO 8601 UTC
    trust_score  REAL,               -- set by EpiRank
    acceptance   TEXT                 -- set by EpiRank
)

links (
    id         TEXT PRIMARY KEY,     -- sha256:... hash
    source_id  TEXT NOT NULL,        -- references nodes(id)
    target_id  TEXT NOT NULL,        -- references nodes(id)
    relation   TEXT NOT NULL,        -- supports, contradicts, ...
    agent_id   TEXT NOT NULL,
    created_at TEXT NOT NULL
)

agents (
    id         TEXT PRIMARY KEY,
    reputation REAL DEFAULT 0.3,
    created_at TEXT NOT NULL
)
```

Indexes on `links(source_id)`, `links(target_id)`, `nodes(node_type)`, `nodes(agent_id)`.

## Content Hashing

Node IDs are computed as `sha256:` + SHA-256 of canonical JSON with sorted keys:

```json
{"agent_id": "...", "content_data": ..., "content_text": "...", "node_type": "..."}
```

The hash includes `agent_id` by design — identical content submitted by different agents produces different IDs. Authorship is part of the identity because trust propagation depends on who authored what.

Link IDs additionally include `created_at`, allowing the same pair of nodes to be linked multiple times (e.g., by different agents or at different times).
