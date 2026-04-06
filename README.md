# Research Evaluation Protocol

Open protocol and MCP server for evaluating AI research agent outputs.

## The Problem

AI research agents generate hundreds of claims per session. No human team can review that volume. Using another LLM to judge is expensive, circular (an LLM judging an LLM), and non-reproducible. This protocol provides **zero-cost structural evaluation** and **graph-based trust propagation** instead — deterministic, auditable, and free of inference costs.

## What is this?

AI research agents generate claims, evidence, and hypotheses at scale. This protocol provides:

1. **Structured Contributions** — Standard format for research outputs
2. **Trust Propagation (EpiRank)** — Distributed trust computation over a knowledge graph
3. **Structural Verification** — Automated integrity checks (no LLM inference, zero cost)
4. **Pattern Detection** — Confirmation bias, self-support, and other anti-patterns

## Quick Start

```bash
# Install
uv add research-eval-protocol

# Run as MCP server (stdio)
uv run research-eval-protocol
```

### Claude Code Integration

Add to `~/.claude/mcp.json`:

```json
{
  "mcpServers": {
    "research-eval": {
      "command": "uv",
      "args": ["--directory", "/path/to/research-eval-protocol", "run", "research-eval-protocol"]
    }
  }
}
```

### Claude Code Skills

Copy skills to your project:

```bash
cp spec/skills/*.md /your-project/.claude/skills/
```

## 30-Second Example

```python
# 1. Submit a claim
result = submit_contribution(
    content_text="LLMs exhibit emergent reasoning at scale via chain-of-thought prompting.",
    contribution_type="claim",
    agent_id="agent-alpha",
    content_data={"assertion": "LLMs show emergent reasoning at scale"},
)
claim_id = result["node_id"]   # sha256:c2d835...

# 2. Submit evidence from a different agent
result = submit_contribution(
    content_text="GPT-4 accuracy on GSM8K improved from 58% to 92% with chain-of-thought.",
    contribution_type="evidence",
    agent_id="agent-beta",
    content_data={"direction": "supports"},
)
evidence_id = result["node_id"]

# 3. Link evidence to claim
submit_link(source_id=evidence_id, target_id=claim_id, relation="supports", agent_id="agent-beta")

# 4. Compute trust — the claim is now supported by independent evidence
trust = compute_trust(node_id=claim_id)
# → claim_trust: 0.82, acceptance: "accepted", patterns: all PASS
```

## MCP Tools

| Tool | Description |
|------|------------|
| `verify_contribution` | Check structural integrity without registering |
| `submit_contribution` | Verify + register in the knowledge graph |
| `submit_link` | Create a typed relationship between Contributions |
| `compute_trust` | Run EpiRank and get trust scores + pattern detection |
| `query_network` | Search the knowledge graph |

## MCP Resources

| Resource | Description |
|----------|------------|
| `protocol://spec/v0.1` | Protocol specification |
| `protocol://types` | Core Contribution types |
| `protocol://relations` | Core Link relations |
| `protocol://skills/contribution-format` | How to format Contributions |
| `protocol://skills/evaluation-interpret` | How to interpret Evaluation Envelopes |

## Core Types (v0.1)

`claim` · `hypothesis` · `evidence` · `method` · `critique` · `observation`

Extensions: `custom:your-type` (permissionless)

## Core Relations (v0.1)

`supports` (+1.0) · `contradicts` (-1.0) · `extends` (+0.7) · `derives-from` (+0.5)

## How EpiRank Works

EpiRank computes trust scores by propagating trust through the knowledge graph:

- **C(n)** — Node trust: computed from incoming links' polarity, temporal decay, source trust, and author reputation
- **R(a)** — Agent reputation: weighted mean of authored nodes' trust scores
- Supported claims gain trust; contradicted claims lose trust
- New agents start at reputation 0.3 (cold start defense)

## Documentation

| Document | Description |
|----------|------------|
| [Why this protocol?](docs/why.md) | Motivation, design philosophy, target users, and concrete scenarios |
| [Architecture](docs/architecture.md) | Data flow, module map, EpiRank details, storage schema |
| [Roadmap](docs/roadmap.md) | v0.1 scope, known limitations, and future directions |
| [Protocol Spec](spec/v0.1/protocol.md) | Formal specification of types, relations, and envelopes |

## License

- Protocol specification (`spec/`): Apache 2.0
- Reference implementation (`src/`): BSL 1.1 (converts to Apache 2.0 after 3 years)
