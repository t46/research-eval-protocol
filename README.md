# Research Evaluation Protocol

Open protocol and MCP server for evaluating AI research agent outputs.

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

## License

- Protocol specification (`spec/`): Apache 2.0
- Reference implementation (`src/`): BSL 1.1 (converts to Apache 2.0 after 3 years)
