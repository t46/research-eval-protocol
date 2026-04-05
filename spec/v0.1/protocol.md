# Research Evaluation Protocol — v0.1

## Overview

The Research Evaluation Protocol is an open standard for evaluating AI research agent outputs.
It provides:

1. **Structured Contributions** — A standard format for research outputs (claims, evidence, hypotheses, etc.)
2. **Typed Links** — Directed relationships between Contributions (supports, contradicts, extends, derives-from)
3. **Structural Verification** — Automated integrity checks with no LLM inference
4. **Trust Propagation (EpiRank)** — Distributed trust computation over the knowledge graph
5. **Evaluation Envelopes** — Structured assessment results combining verification + trust + metadata

## Core Primitives

### Contribution

A unit of research output. Has:
- `content_text` — Main textual content
- `content_data` — Optional structured data (type-specific)
- `contribution_type` — One of 6 core types or `custom:*` extension
- `agent_id` — Identity of the authoring agent
- `id` — Content-hash (SHA-256 of canonical JSON)

### Link

A typed, directed relationship between two Contributions. Has:
- `source_id` — Content-hash of source
- `target_id` — Content-hash of target
- `relation` — One of 4 core relations or `custom:*` extension
- `agent_id` — Identity of the agent creating the link

### Identity

A persistent agent identifier with type (human / agent / organization).

## Core Types (v0.1)

| Type | Description |
|------|------------|
| `claim` | Verifiable factual assertion |
| `hypothesis` | Unverified predictive assertion |
| `evidence` | Data or argument supporting/refuting another Contribution |
| `method` | Reusable procedure or technique |
| `critique` | Problem identification in existing Contributions |
| `observation` | Raw, theory-neutral recording |

Extensions: `custom:your-type-name` (permissionless, immediate)

## Core Relations (v0.1)

| Relation | Polarity | Direction |
|----------|----------|-----------|
| `supports` | +1.0 | A → B (A increases justification of B) |
| `contradicts` | -1.0 | A → B (A decreases justification of B) |
| `extends` | +0.7 | A → B (A develops/refines B) |
| `derives-from` | +0.5 | A → B (A logically follows from B) |

## Evaluation Envelope

Every verified Contribution receives an Evaluation Envelope:

```yaml
structural:
  checks: [{id, status, reason}, ...]
  overall: PASS | FLAG | BLOCK

trust:
  claim_trust: 0.0 - 1.0
  agent_reputation: 0.0 - 1.0
  acceptance: accepted | contested | rejected | uncertain

meta:
  connectivity: int
  reproducibility_status: verified | challenged | untested | not-applicable
```

## EpiRank Algorithm

Trust propagation through the knowledge graph:
- **C(n)**: Node trust score — computed from incoming link polarity, temporal decay, source trust, and author reputation
- **R(a)**: Agent reputation — weighted mean of authored nodes' trust scores
- Parameters: α=3.0 (sigmoid steepness), β=0.85 (damping), t½=365 days

## Licensing

- Protocol specification: Apache 2.0
- Reference implementation: BSL 1.1 (converts to Apache 2.0 after 3 years)
