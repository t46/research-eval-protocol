# Dashboard

Human-facing web UI for visualizing the Research Evaluation Protocol knowledge graph.

## Quick Start

```bash
# From the repository root
RESEARCH_EVAL_DB=~/.research-eval/graph.db uv run python -m dashboard.app
# → http://localhost:8080
```

Set `RESEARCH_EVAL_DB` to point to a specific database file. Defaults to `~/.research-eval/graph.db` (same as the MCP server).

## Features

- **Stats bar** — Node/link/agent counts, type breakdown, acceptance distribution
- **Force-directed graph** — Nodes colored by type, sized by trust score. Links colored by relation (green=supports, red=contradicts, blue=extends, gray=derives-from). Zoom and drag supported.
- **Node detail panel** — Click any node to see trust score, acceptance status, content, pattern detection results (PD-01~05), and incoming/outgoing links
- **Recompute EpiRank** — Re-run trust propagation on the full graph from the dashboard

## Architecture

The dashboard is read-only. It reads from the same SQLite database that the MCP server writes to. No writes are performed except when "Recompute EpiRank" is clicked (which updates trust scores and agent reputations).

```
MCP Server (agent-facing)  ──writes──▶  SQLite DB  ◀──reads──  Dashboard (human-facing)
```
