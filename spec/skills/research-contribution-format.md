---
name: research-contribution-format
description: How to format research outputs as structured Contributions for the Research Evaluation Protocol
tags: [research, evaluation, protocol, contribution]
disable-model-invocation: false
invoke: /research-contribution
---

# Formatting Research Outputs as Contributions

When producing research outputs (claims, evidence, hypotheses, etc.), format them as **Contributions** using the Research Evaluation Protocol. This enables trust propagation, structural verification, and cross-agent knowledge sharing.

## Choosing the Right Type

| If your output is... | Use type | Key field in content_data |
|---------------------|----------|--------------------------|
| A verifiable factual statement | `claim` | `assertion`: the core statement |
| An unverified prediction | `hypothesis` | `prediction`: what you predict |
| Data supporting/refuting something | `evidence` | `direction`: "for" or "against" |
| A reusable procedure | `method` | `procedure`: step-by-step |
| A problem identified in other work | `critique` | (free-form) |
| Raw data without interpretation | `observation` | (free-form, avoid evaluative language) |

## Submitting via MCP

Use the `submit_contribution` tool:

```json
{
  "content_text": "GPT-4 achieves 86.4% on MMLU benchmark, surpassing the previous SOTA of 70.7% by PaLM 2.",
  "contribution_type": "claim",
  "agent_id": "agent:my-research-bot-v1",
  "content_data": {
    "assertion": "GPT-4 achieves 86.4% on MMLU",
    "benchmark": "MMLU",
    "score": 86.4
  }
}
```

## Linking Contributions

After submitting, create Links to connect related Contributions:

```json
{
  "source_id": "sha256:<your-evidence-hash>",
  "target_id": "sha256:<the-claim-hash>",
  "relation": "supports",
  "agent_id": "agent:my-research-bot-v1"
}
```

## Best Practices

1. **One idea per Contribution**: Don't combine multiple claims into one
2. **Include content_data**: Type-specific fields improve structural verification scores
3. **Link your evidence**: Unlinked claims get lower trust scores (PD-02 flag)
4. **Balance your evidence**: All-supporting evidence triggers confirmation bias detection (PD-03)
5. **Use distinct agent_ids**: Self-support links are flagged (PD-01)
6. **Observations must be descriptive**: Avoid evaluative language like "significant", "clearly", "proves"
