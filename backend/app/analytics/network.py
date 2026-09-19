"""
Link Analysis & Network Topology (Section 7-E).

Build the interaction graph from `interactions`, compute PageRank,
betweenness, eigenvector, and degree centrality, run Louvain community
detection, and combine centralities into a configurable-weight composite
Influence Score.

Causal influence scoring (Independent Cascade node-removal simulation) and
Propagation Replay are build-order step 8, not here — this module only
covers the graph/centrality/community half of Section 7-E.
"""
import uuid

import networkx as nx
from networkx.algorithms.community import louvain_communities
from sqlalchemy.orm import Session

from app.models import Interaction, Community, UserCommunityMembership
from app.blockchain.ledger import append_block

# Default composite Influence Score weights. Section 10 lists
# "influence-score weight configuration" as a Settings-page feature — this
# is the default; a future Settings page can pass overrides into
# `compute_influence_scores` instead of hardcoding new defaults here.
DEFAULT_INFLUENCE_WEIGHTS = {
    "pagerank": 0.35,
    "betweenness": 0.25,
    "eigenvector": 0.25,
    "degree": 0.15,
}


def build_graph(db: Session) -> nx.DiGraph:
    """Directed, weighted graph: edge weight = sum of interaction weights
    for that (source, target, type) triple collapsed across type."""
    graph = nx.DiGraph()
    interactions = db.query(Interaction).all()
    for interaction in interactions:
        if graph.has_edge(interaction.source_user, interaction.target_user):
            graph[interaction.source_user][interaction.target_user]["weight"] += interaction.weight
        else:
            graph.add_edge(interaction.source_user, interaction.target_user, weight=interaction.weight)
    return graph


def compute_centralities(graph: nx.DiGraph) -> dict[str, dict[str, float]]:
    if graph.number_of_nodes() == 0:
        return {"pagerank": {}, "betweenness": {}, "eigenvector": {}, "degree": {}}

    pagerank = nx.pagerank(graph, weight="weight")
    betweenness = nx.betweenness_centrality(graph, weight="weight", normalized=True)
    degree = nx.degree_centrality(graph)
    try:
        eigenvector = nx.eigenvector_centrality(graph, weight="weight", max_iter=500)
    except nx.PowerIterationFailedConvergence:
        # Sparse/disconnected graphs can fail to converge — fall back to 0s
        # rather than letting the whole analysis run error out.
        eigenvector = {node: 0.0 for node in graph.nodes}

    return {
        "pagerank": pagerank,
        "betweenness": betweenness,
        "eigenvector": eigenvector,
        "degree": degree,
    }


def _normalize(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    if hi == lo:
        return {k: 0.0 for k in values}
    return {k: (v - lo) / (hi - lo) for k, v in values.items()}


def compute_influence_scores(
    centralities: dict[str, dict[str, float]],
    weights: dict[str, float] | None = None,
) -> dict[str, float]:
    """Min-max normalize each centrality independently (so no single metric's
    natural scale dominates), then combine with `weights`."""
    weights = weights or DEFAULT_INFLUENCE_WEIGHTS
    normalized = {name: _normalize(vals) for name, vals in centralities.items()}

    all_nodes = set()
    for vals in centralities.values():
        all_nodes |= set(vals.keys())

    scores = {}
    for node in all_nodes:
        score = sum(weights.get(name, 0.0) * normalized[name].get(node, 0.0) for name in normalized)
        scores[node] = round(score, 4)
    return scores


def detect_communities(graph: nx.DiGraph) -> dict[str, int]:
    """Louvain runs on undirected graphs — collapse direction, keep weight."""
    if graph.number_of_nodes() == 0:
        return {}
    undirected = graph.to_undirected()
    communities = louvain_communities(undirected, weight="weight", seed=42)
    assignment = {}
    for idx, community_nodes in enumerate(communities):
        for node in community_nodes:
            assignment[node] = idx
    return assignment


def persist_communities(db: Session, community_assignment: dict[str, int]) -> str:
    """Writes to `communities` + `user_community_membership`, per Section 9.
    Each run gets its own algorithm_run_id so history isn't overwritten."""
    run_id = str(uuid.uuid4())
    community_id_by_label: dict[int, str] = {}

    for label_idx in set(community_assignment.values()):
        community = Community(label=f"community_{label_idx}", algorithm_run_id=run_id)
        db.add(community)
        db.flush()  # populate community.id before we reference it below
        community_id_by_label[label_idx] = community.id

    for user_handle, label_idx in community_assignment.items():
        db.add(UserCommunityMembership(
            user_handle=user_handle,
            community_id=community_id_by_label[label_idx],
        ))

    db.commit()
    return run_id


def run_full_analysis(db: Session) -> dict:
    """Orchestrates build -> communities -> persist -> ledger checkpoint.
    Does NOT compute/return influence scores -- those are live-computed
    on demand by get_graph_payload() (see GET /network/graph), which is
    also where configurable weights (Section 10) actually take effect.
    Community detection (Louvain) is the one part of this pipeline
    expensive enough to be worth persisting rather than recomputing
    on every graph view."""
    graph = build_graph(db)
    community_assignment = detect_communities(graph)
    run_id = persist_communities(db, community_assignment)

    append_block(db, "NETWORK_ANALYSIS_RUN", {
        "run_id": run_id,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "community_count": len(set(community_assignment.values())) if community_assignment else 0,
    })

    return {
        "run_id": run_id,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "community_count": len(set(community_assignment.values())) if community_assignment else 0,
    }


def get_graph_payload(db: Session, weights: dict[str, float] | None = None) -> dict:
    """Live-computed (not persisted) view for the frontend — centralities +
    influence score + the most recent persisted community assignment, in
    Cytoscape.js node/edge shape."""
    graph = build_graph(db)
    centralities = compute_centralities(graph)
    influence = compute_influence_scores(centralities, weights)

    # Most recent community run, if one has ever been persisted.
    latest_community = (
        db.query(Community).order_by(Community.created_at.desc()).first()
    )
    community_by_user: dict[str, str] = {}
    if latest_community:
        memberships = (
            db.query(UserCommunityMembership, Community)
            .join(Community, UserCommunityMembership.community_id == Community.id)
            .filter(Community.algorithm_run_id == latest_community.algorithm_run_id)
            .all()
        )
        for membership, community in memberships:
            community_by_user[membership.user_handle] = community.label

    nodes = [
        {
            "data": {
                "id": node,
                "label": node,
                "pagerank": round(centralities["pagerank"].get(node, 0.0), 4),
                "betweenness": round(centralities["betweenness"].get(node, 0.0), 4),
                "eigenvector": round(centralities["eigenvector"].get(node, 0.0), 4),
                "degree": round(centralities["degree"].get(node, 0.0), 4),
                "influence_score": influence.get(node, 0.0),
                "community": community_by_user.get(node, "unassigned"),
            }
        }
        for node in graph.nodes
    ]
    edges = [
        {"data": {"source": u, "target": v, "weight": round(data.get("weight", 1.0), 2)}}
        for u, v, data in graph.edges(data=True)
    ]

    mode = "static_sample" if graph.number_of_nodes() == 0 else "computed"
    return {"mode": mode, "nodes": nodes, "edges": edges}
