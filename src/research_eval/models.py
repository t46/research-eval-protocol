"""Core data models for the Research Evaluation Protocol v0.1."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --- Enums ---


class ContributionType(str, Enum):
    CLAIM = "claim"
    HYPOTHESIS = "hypothesis"
    EVIDENCE = "evidence"
    METHOD = "method"
    CRITIQUE = "critique"
    OBSERVATION = "observation"


class LinkRelation(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DERIVES_FROM = "derives-from"
    EXTENDS = "extends"


class CheckStatus(str, Enum):
    PASS = "PASS"
    FLAG = "FLAG"
    BLOCK = "BLOCK"


class AcceptanceStatus(str, Enum):
    ACCEPTED = "accepted"
    CONTESTED = "contested"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"


class ReproducibilityStatus(str, Enum):
    VERIFIED = "verified"
    CHALLENGED = "challenged"
    UNTESTED = "untested"
    NOT_APPLICABLE = "not-applicable"


# --- Polarity mapping (EpiRank) ---

POLARITY: dict[LinkRelation, float] = {
    LinkRelation.SUPPORTS: 1.0,
    LinkRelation.CONTRADICTS: -1.0,
    LinkRelation.EXTENDS: 0.7,
    LinkRelation.DERIVES_FROM: 0.5,
}

# --- Type-based priors for EpiRank (isolated nodes) ---

TYPE_PRIOR: dict[ContributionType, float] = {
    ContributionType.CLAIM: 0.4,
    ContributionType.HYPOTHESIS: 0.3,
    ContributionType.EVIDENCE: 0.5,
    ContributionType.METHOD: 0.5,
    ContributionType.CRITIQUE: 0.5,
    ContributionType.OBSERVATION: 0.6,
}


# --- Content-hash computation ---


def compute_node_hash(
    content_text: str,
    content_data: dict[str, Any] | None,
    node_type: str,
    agent_id: str,
) -> str:
    canonical = json.dumps(
        {
            "content_text": content_text,
            "content_data": content_data,
            "node_type": node_type,
            "agent_id": agent_id,
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_link_hash(
    source_id: str,
    target_id: str,
    relation: str,
    agent_id: str,
    created_at: str,
) -> str:
    canonical = json.dumps(
        {
            "source_node_id": source_id,
            "target_node_id": target_id,
            "relation": relation,
            "agent_id": agent_id,
            "created_at": created_at,
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --- Input models ---


class ContributionInput(BaseModel):
    """Input for submitting or verifying a Contribution."""

    content_text: str = Field(description="Main textual content of the contribution")
    content_data: dict[str, Any] | None = Field(
        default=None, description="Structured data (type-specific fields)"
    )
    contribution_type: str = Field(description="Type from registry or custom:* prefix")
    agent_id: str = Field(description="Identity of the authoring agent")


class LinkInput(BaseModel):
    """Input for submitting a Link between two Contributions."""

    source_id: str = Field(description="Content-hash ID of the source node")
    target_id: str = Field(description="Content-hash ID of the target node")
    relation: str = Field(description="Relation type from registry or custom:* prefix")
    agent_id: str = Field(description="Identity of the agent creating this link")


# --- Evaluation Envelope ---


class CheckResult(BaseModel):
    id: str
    status: CheckStatus
    reason: str


class StructuralVerification(BaseModel):
    checks: list[CheckResult]
    overall: CheckStatus


class TrustScores(BaseModel):
    claim_trust: float = Field(ge=0.0, le=1.0)
    agent_reputation: float = Field(ge=0.0, le=1.0)
    acceptance: AcceptanceStatus


class MetaDimensions(BaseModel):
    connectivity: int = Field(ge=0)
    reproducibility_status: ReproducibilityStatus = ReproducibilityStatus.UNTESTED


class EvaluationEnvelope(BaseModel):
    structural: StructuralVerification
    trust: TrustScores | None = None
    meta: MetaDimensions | None = None


# --- Stored models ---


class StoredNode(BaseModel):
    id: str
    node_type: str
    agent_id: str
    content_text: str
    content_data: dict[str, Any] | None = None
    created_at: str
    trust_score: float | None = None
    acceptance: str | None = None


class StoredLink(BaseModel):
    id: str
    source_id: str
    target_id: str
    relation: str
    agent_id: str
    created_at: str


class StoredAgent(BaseModel):
    id: str
    reputation: float = 0.3
    created_at: str


# --- Helper ---


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
