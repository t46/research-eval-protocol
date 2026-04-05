"""Smoke tests for the Research Evaluation Protocol MVP."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from research_eval.models import (
    CheckStatus,
    ContributionInput,
    compute_node_hash,
)
from research_eval.storage import GraphStore
from research_eval.verification import verify
from research_eval.epirank import run_epirank
from research_eval.patterns import detect_patterns
from research_eval.models import LinkInput


@pytest.fixture
def store(tmp_path: Path) -> GraphStore:
    return GraphStore(tmp_path / "test.db")


# --- Models ---


def test_compute_node_hash_deterministic():
    h1 = compute_node_hash("test content here!!!", None, "claim", "agent-1")
    h2 = compute_node_hash("test content here!!!", None, "claim", "agent-1")
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_compute_node_hash_varies_with_agent():
    h1 = compute_node_hash("test content here!!!", None, "claim", "agent-1")
    h2 = compute_node_hash("test content here!!!", None, "claim", "agent-2")
    assert h1 != h2


# --- Verification ---


def test_verify_valid_claim():
    inp = ContributionInput(
        content_text="GPT-4 achieves 86.4% on the MMLU benchmark, setting a new state of the art.",
        contribution_type="claim",
        agent_id="agent-1",
        content_data={"assertion": "GPT-4 achieves 86.4% on MMLU"},
    )
    result = verify(inp)
    assert result.overall == CheckStatus.PASS


def test_verify_empty_content_blocks():
    inp = ContributionInput(
        content_text="",
        contribution_type="claim",
        agent_id="agent-1",
    )
    result = verify(inp)
    assert result.overall == CheckStatus.BLOCK


def test_verify_invalid_type_blocks():
    inp = ContributionInput(
        content_text="This is a valid length content text for testing.",
        contribution_type="not-a-real-type",
        agent_id="agent-1",
    )
    result = verify(inp)
    assert result.overall == CheckStatus.BLOCK


def test_verify_custom_type_flags():
    inp = ContributionInput(
        content_text="This is a valid length content text for testing.",
        contribution_type="custom:my-new-type",
        agent_id="agent-1",
    )
    result = verify(inp)
    assert result.overall == CheckStatus.FLAG


def test_verify_observation_evaluative_flags():
    inp = ContributionInput(
        content_text="The results clearly demonstrate a significant improvement in performance across all metrics.",
        contribution_type="observation",
        agent_id="agent-1",
    )
    result = verify(inp)
    ic05 = next(c for c in result.checks if c.id == "IC-05")
    assert ic05.status == CheckStatus.FLAG


# --- Storage ---


def test_storage_insert_and_retrieve(store: GraphStore):
    inp = ContributionInput(
        content_text="Neural scaling laws follow a power-law relationship with model size.",
        contribution_type="claim",
        agent_id="agent-1",
        content_data={"assertion": "Scaling laws are power-law"},
    )
    node = store.insert_node(inp)
    assert node.id.startswith("sha256:")

    retrieved = store.get_node(node.id)
    assert retrieved is not None
    assert retrieved.content_text == inp.content_text


def test_storage_link_creation(store: GraphStore):
    claim = store.insert_node(ContributionInput(
        content_text="Transformer models exhibit emergent abilities at sufficient scale.",
        contribution_type="claim",
        agent_id="agent-1",
    ))
    evidence = store.insert_node(ContributionInput(
        content_text="We observed that chain-of-thought reasoning only appears in models with >100B parameters across 5 benchmark tasks.",
        contribution_type="evidence",
        agent_id="agent-2",
        content_data={"direction": "for"},
    ))
    link = store.insert_link(LinkInput(
        source_id=evidence.id,
        target_id=claim.id,
        relation="supports",
        agent_id="agent-2",
    ))
    assert link.id.startswith("sha256:")

    incoming = store.get_incoming_links(claim.id)
    assert len(incoming) == 1
    assert incoming[0].relation == "supports"


# --- EpiRank ---


def test_epirank_supported_claim_gains_trust(store: GraphStore):
    claim = store.insert_node(ContributionInput(
        content_text="Retrieval-augmented generation reduces hallucination rates in LLM outputs.",
        contribution_type="claim",
        agent_id="agent-1",
        content_data={"assertion": "RAG reduces hallucination"},
    ))
    ev1 = store.insert_node(ContributionInput(
        content_text="In our experiment with 1000 queries, RAG-augmented GPT-4 hallucinated 12% less than baseline.",
        contribution_type="evidence",
        agent_id="agent-2",
        content_data={"direction": "for"},
    ))
    ev2 = store.insert_node(ContributionInput(
        content_text="Meta-analysis of 15 studies shows consistent reduction in factual errors when using retrieval augmentation.",
        contribution_type="evidence",
        agent_id="agent-3",
        content_data={"direction": "for"},
    ))
    store.insert_link(LinkInput(source_id=ev1.id, target_id=claim.id, relation="supports", agent_id="agent-2"))
    store.insert_link(LinkInput(source_id=ev2.id, target_id=claim.id, relation="supports", agent_id="agent-3"))

    scores = run_epirank(store)
    # Claim should have higher trust than baseline (0.5) due to support
    assert scores[claim.id] > 0.5


def test_epirank_contradicted_claim_loses_trust(store: GraphStore):
    claim = store.insert_node(ContributionInput(
        content_text="Larger language models always produce more accurate outputs than smaller ones.",
        contribution_type="claim",
        agent_id="agent-1",
        content_data={"assertion": "Bigger is always better"},
    ))
    contra = store.insert_node(ContributionInput(
        content_text="We found that a fine-tuned 7B model outperforms GPT-4 on domain-specific medical QA tasks.",
        contribution_type="evidence",
        agent_id="agent-2",
        content_data={"direction": "against"},
    ))
    store.insert_link(LinkInput(source_id=contra.id, target_id=claim.id, relation="contradicts", agent_id="agent-2"))

    scores = run_epirank(store)
    # Claim should have lower trust than baseline due to contradiction
    assert scores[claim.id] < 0.5


# --- Patterns ---


def test_pattern_confirmation_bias(store: GraphStore):
    claim = store.insert_node(ContributionInput(
        content_text="Attention mechanisms are the key innovation behind transformer model success.",
        contribution_type="claim",
        agent_id="agent-1",
    ))
    for i in range(3):
        ev = store.insert_node(ContributionInput(
            content_text=f"Evidence {i}: Ablation study showing attention is critical for performance on benchmark {i}.",
            contribution_type="evidence",
            agent_id=f"agent-{i+2}",
            content_data={"direction": "for"},
        ))
        store.insert_link(LinkInput(source_id=ev.id, target_id=claim.id, relation="supports", agent_id=f"agent-{i+2}"))

    results = detect_patterns(store, claim.id)
    pd03 = next(r for r in results if r.id == "PD-03")
    assert pd03.status == CheckStatus.FLAG


# --- E2E scenario ---


def test_e2e_submit_verify_trust(store: GraphStore):
    """Full scenario: submit claim, add evidence, check trust changes."""
    # Submit a claim
    claim_inp = ContributionInput(
        content_text="In-context learning in LLMs does not require gradient updates to model parameters.",
        contribution_type="claim",
        agent_id="researcher-alpha",
        content_data={"assertion": "ICL needs no gradient updates"},
    )
    structural = verify(claim_inp)
    assert structural.overall == CheckStatus.PASS

    claim = store.insert_node(claim_inp)
    scores_before = run_epirank(store)

    # Add supporting evidence from a different agent
    evidence_inp = ContributionInput(
        content_text="Mechanistic interpretability analysis reveals that ICL operates via induction heads without weight modification.",
        contribution_type="evidence",
        agent_id="researcher-beta",
        content_data={"direction": "for"},
    )
    evidence = store.insert_node(evidence_inp)
    store.insert_link(LinkInput(
        source_id=evidence.id,
        target_id=claim.id,
        relation="supports",
        agent_id="researcher-beta",
    ))

    scores_after = run_epirank(store)
    # Trust should increase after adding supporting evidence
    assert scores_after[claim.id] >= scores_before[claim.id]
