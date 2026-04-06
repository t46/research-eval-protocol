# Roadmap

## v0.1 — Current Scope

v0.1 is a local, single-machine MVP. It implements the core protocol primitives and a minimal but functional trust propagation algorithm.

**What is implemented:**
- 6 core contribution types + `custom:*` extensions
- 4 core link relations + `custom:*` extensions
- 5 structural integrity checks (IC-01 through IC-05)
- 5 graph-structural pattern detections (PD-01 through PD-05)
- EpiRank trust propagation with node trust C(n) and agent reputation R(a)
- SQLite graph store at `~/.research-eval/graph.db`
- MCP server (stdio transport) with 5 tools and 5 resources

**What is not implemented:**
- Networking, federation, or multi-user access
- Authentication or agent identity verification
- EpiRank extensions (independence bonus, calibration, Sybil detection)

## Known Limitations

- **Full-graph recomputation.** `run_epirank()` iterates over all nodes and links on every call. This is fine for thousands of nodes, but will not scale to millions.
- **No independence bonus.** Two agents from the same organization are treated as fully independent. Evidence from related agents should carry less weight, but v0.1 does not model organizational relationships.
- **No calibration.** Trust scores are relative within the graph. A score of 0.8 means "well-supported by the current evidence network," not "80% likely to be true."
- **No Sybil detection.** A bad actor can create many agent IDs to inflate trust through self-support. PD-01 catches direct self-support, but not coordinated multi-agent inflation.
- **Single-process SQLite.** WAL mode allows concurrent reads, but only one process can write at a time.

## Future Directions

### Independence Bonus
Weight evidence higher when it comes from agents with no organizational or training relationship to the claim's author. This reduces the value of self-reinforcing clusters.

### Calibration
Anchor trust scores against known-true and known-false benchmark contributions. This gives trust scores an absolute meaning rather than a graph-relative one.

### Sybil Detection
Detect clusters of agents that exclusively support each other. Use graph topology (e.g., spectral clustering on the support subgraph) to flag suspicious coordination patterns.

### Federated Graphs
Share knowledge graphs across organizations using content-addressed IDs as join keys. A contribution's SHA-256 hash is the same regardless of where it is stored, enabling cross-graph references without a central registry.

### Incremental EpiRank
Update trust scores incrementally when a single link is added, instead of recomputing the full graph. Propagate changes only through the affected subgraph.
