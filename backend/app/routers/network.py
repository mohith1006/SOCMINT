from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
import uuid

from app.database import get_db
from app.deps import get_current_user, require_role
from app.models import User, UserRole, NodeInfluenceScore
from app.analytics.network import (
    run_full_analysis, get_graph_payload, build_graph, compute_centralities, compute_influence_scores,
    DEFAULT_INFLUENCE_WEIGHTS,
)
from app.analytics.causal_impact import (
    compute_causal_impact_scores, persist_causal_impact_scores,
    DEFAULT_PROPAGATION_PROB, DEFAULT_TRIALS, MAX_TRIALS, MAX_CANDIDATES,
)
from app.analytics.propagation import get_propagation_replay

router = APIRouter(prefix="/network", tags=["network"])

require_analyst_or_above = require_role(UserRole.ADMIN, UserRole.ANALYST, UserRole.INVESTIGATOR)


class InfluenceWeights(BaseModel):
    pagerank: float | None = None
    betweenness: float | None = None
    eigenvector: float | None = None
    degree: float | None = None

    def as_dict(self) -> dict[str, float] | None:
        provided = {k: v for k, v in self.model_dump().items() if v is not None}
        return provided or None


@router.get("/graph")
def network_graph(
    pagerank: float | None = Query(None, ge=0.0, le=1.0),
    betweenness: float | None = Query(None, ge=0.0, le=1.0),
    eigenvector: float | None = Query(None, ge=0.0, le=1.0),
    degree: float | None = Query(None, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Live-computed graph for Cytoscape.js — centralities + composite
    influence score + most recent persisted Louvain community per node.
    Optional weight query params (Section 10's "configurable influence-
    score weights") override DEFAULT_INFLUENCE_WEIGHTS for just this
    request — any omitted weight falls back to its default rather than
    zeroing out, so a caller only needs to specify the ones they want
    to change."""
    custom_weights = InfluenceWeights(
        pagerank=pagerank, betweenness=betweenness, eigenvector=eigenvector, degree=degree
    ).as_dict()
    weights = {**DEFAULT_INFLUENCE_WEIGHTS, **custom_weights} if custom_weights else None
    return get_graph_payload(db, weights)


@router.post("/analyze")
def analyze_network(
    db: Session = Depends(get_db),
    _user: User = Depends(require_analyst_or_above),
):
    """Rebuilds the graph, recomputes communities, persists a new
    community-assignment run, and writes a ledger checkpoint. Gated to
    Analyst/Investigator/Admin — Viewers can read the graph but not trigger
    a (potentially expensive) recompute. Does not take influence-score
    weights — see GET /network/graph for those (computed live, not
    something this persisted run needs to store)."""
    return run_full_analysis(db)


@router.post("/causal-impact")
def analyze_causal_impact(
    top_n: int = Query(10, ge=1, le=MAX_CANDIDATES),
    trials: int = Query(DEFAULT_TRIALS, ge=1, le=MAX_TRIALS),
    propagation_prob: float = Query(DEFAULT_PROPAGATION_PROB, gt=0.0, le=1.0),
    db: Session = Depends(get_db),
    _user: User = Depends(require_analyst_or_above),
):
    """Independent Cascade node-removal simulation (Section 7-E) for the
    `top_n` highest-Influence-Score nodes. Monte Carlo trials scale
    compute cost roughly linearly — keep `trials` modest for large graphs.
    See app/analytics/causal_impact.py for the method and its caveats."""
    graph = build_graph(db)
    centralities = compute_centralities(graph)
    influence = compute_influence_scores(centralities)
    candidate_nodes = sorted(influence, key=influence.get, reverse=True)[:top_n]

    scores = compute_causal_impact_scores(graph, candidate_nodes, propagation_prob, trials)
    run_id = str(uuid.uuid4())
    persist_causal_impact_scores(db, scores, run_id)

    return {"run_id": run_id, "propagation_prob": propagation_prob, "trials": trials, "scores": scores}


@router.get("/causal-impact")
def latest_causal_impact(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Most recently persisted causal_impact_score per node."""
    latest = db.query(NodeInfluenceScore).order_by(NodeInfluenceScore.computed_at.desc()).first()
    if not latest:
        return {"mode": "static_sample", "run_id": None, "scores": []}

    rows = (
        db.query(NodeInfluenceScore)
        .filter(NodeInfluenceScore.algorithm_run_id == latest.algorithm_run_id)
        .order_by(NodeInfluenceScore.causal_impact_score.desc())
        .all()
    )
    return {
        "mode": "computed",
        "run_id": latest.algorithm_run_id,
        "scores": [{"node": r.node_handle, "causal_impact_score": r.causal_impact_score} for r in rows],
    }


@router.get("/propagation-replay/{topic_id}")
def propagation_replay(
    topic_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Time-ordered reconstruction of a topic's spread across communities
    (Section 7-E), for frontend animation."""
    return get_propagation_replay(db, topic_id)
