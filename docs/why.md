# Why Research Evaluation Protocol?

## The Scale Problem

AI research agents can generate hundreds of claims, hypotheses, and evidence fragments in a single session. A multi-agent pipeline running overnight might produce thousands. No human team can review that volume — and without review, you cannot tell which outputs are well-founded and which are noise.

The bottleneck in AI-assisted research is no longer generation. It is evaluation.

## Why Not LLM-as-Judge?

The most obvious approach — calling another LLM to evaluate the outputs — has three problems:

1. **Cost.** Every evaluation is an inference call. At scale, the evaluation budget rivals the generation budget.
2. **Circularity.** You are trusting an LLM to judge an LLM. The evaluator has the same failure modes (hallucination, sycophancy, pattern matching) as the generator. This does not increase confidence; it launders it.
3. **Non-reproducibility.** The same input can produce different verdicts across runs, models, and prompt variations. You cannot audit or replay the evaluation.

This protocol takes a different path: **structural verification (zero inference cost) combined with graph-based trust propagation (deterministic and auditable).**

## Design Principles

### Zero-cost verification first

The 5 integrity checks (IC-01 through IC-05) and 5 pattern detections (PD-01 through PD-05) run with no LLM calls. They use simple rules to catch structural problems: empty content, missing fields, self-support, confirmation bias, dangling references. These checks are instant, reproducible, and free.

### Graph-based trust, not point scores

Trust is not a property of a single contribution. It emerges from the network of relationships. EpiRank propagates trust through the graph like PageRank propagates authority through the web. A claim supported by strong evidence from reputable agents earns trust. A claim contradicted by credible critiques loses it. The math is transparent and auditable.

### Content-addressed identity

Every contribution receives a SHA-256 hash of its canonical JSON as its ID. This makes contributions immutable, deduplicatable, and independently verifiable — no central registry required. This is also the foundation for future federated graphs, where different organizations can reference each other's contributions by hash.

### Scientific method as type system

The six core types — `claim`, `hypothesis`, `evidence`, `method`, `critique`, `observation` — map directly to the components of scientific reasoning. This is not arbitrary taxonomy. It enables meaningful structural checks: hypotheses should have evidence, observations should be free of evaluative language, claims should not go unsupported.

### Permissionless extensibility

The `custom:` prefix on types and relations lets anyone extend the protocol without coordination. No committee approval, no registry, no versioning friction. Core types provide structure; custom types provide freedom.

## Who Is This For?

- **Developers building AI research agents** who want quality signals on their agent's outputs without adding another LLM call.
- **Teams running multi-agent research pipelines** (e.g., one agent generates hypotheses, another gathers evidence, a third critiques) who need to understand which outputs are well-supported across independent agents.
- **Researchers using AI assistants** who want to filter large volumes of AI-generated research output by trust score, surfacing only the most credible findings for human review.

## Concrete Scenarios

### Single-agent research loop

An agent exploring a topic submits claims and evidence as it works, linking them as it goes. After each research phase, it calls `compute_trust` to see which claims are well-supported and which remain uncertain. It uses trust scores to decide which threads to pursue further and which to abandon.

### Multi-agent pipeline

Agent A generates hypotheses. Agent B gathers evidence from data sources. Agent C critiques the hypotheses against the evidence. The knowledge graph reveals which hypotheses are well-supported across independent agents. Self-support patterns (PD-01) are automatically flagged, so you know when an agent is only citing its own work.

### Human-in-the-loop triage

A researcher runs a multi-agent session overnight. In the morning, they call `query_network` with `min_trust=0.7` to surface only high-confidence, accepted claims. Instead of reading 500 outputs, they review 30 — the ones the evidence network considers most credible.
