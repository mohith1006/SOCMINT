"""
Causal influence scoring (Section 7-E): "Independent Cascade node-removal
simulation for top candidate nodes, stored as causal_impact_score."

Method: seed a cascade from the full set of top candidate nodes (the
network's highest-Influence-Score spreaders, from app/analytics/network.py)
and Monte-Carlo-estimate the expected total reach. Then, for each candidate
individually, remove just that node from the graph, reseed the cascade from
the remaining candidates, and re-estimate reach. The drop in expected reach
when a node is removed IS its causal_impact_score — a direct, literal
reading of "node-removal simulation": how much smaller does the cascade get
without this specific node, holding everything else about the seed set
fixed.

This is a genuine (if computationally simplified) causal estimate, not a
restatement of centrality — a node can have modest PageRank but sit in a
structural position (e.g. a bridge between two dense communities) where
removing it measurably shrinks the cascade, and vice versa.

Propagation probability per edge defaults to a flat 0.1, lightly scaled by
edge weight and capped at 1.0 — a modeling choice, not a measured value
from real diffusion data. Tune `propagation_prob` per deployment once real
cascade data is available to calibrate against.
"""
import random

import networkx as nx
from sqlalchemy.orm import Session

from app.models import NodeInfluenceScore
from app.blockchain.ledger import append_block

DEFAULT_PROPAGATION_PROB = 0.1
DEFAULT_TRIALS = 100
MAX_TRIALS = 500
MAX_CANDIDATES = 50


def independent_cascade_spread(
    graph: nx.DiGraph,
    seeds: list[str],
    propagation_prob: float = DEFAULT_PROPAGATION_PROB,
    trials: int = DEFAULT_TRIALS,
    rng_seed: int | None = None,
) -> float:
    """Monte Carlo estimate of expected total activated nodes when a
    cascade starts from `seeds`. Independent Cascade model: each
    newly-activated node gets exactly one attempt per outgoing edge to
    activate that neighbor, with probability `propagation_prob` (scaled by
    edge weight, capped at 1.0)."""
    rng = random.Random(rng_seed)
    valid_seeds = [s for s in seeds if s in graph.nodes]
    if not valid_seeds:
        return 0.0

    total = 0
    for _ in range(trials):
        activated = set(valid_seeds)
        frontier = list(activated)
        while frontier:
            next_frontier = []
            for node in frontier:
                for neighbor in graph.successors(node):
                    if neighbor in activated:
                        continue
                    weight = graph[node][neighbor].get("weight", 1.0)
                    prob = min(1.0, propagation_prob * weight)
                    if rng.random() < prob:
                        activated.add(neighbor)
                        next_frontier.append(neighbor)
            frontier = next_frontier
        total += len(activated)
    return total / trials


def compute_causal_impact_scores(
    graph: nx.DiGraph,
    candidate_nodes: list[str],
    propagation_prob: float = DEFAULT_PROPAGATION_PROB,
    trials: int = DEFAULT_TRIALS,
    seed: int = 42,
) -> dict[str, float]:
    """For each node in `candidate_nodes`: baseline expected spread seeded
    from the full candidate set, minus expected spread with that one node
    removed. Larger delta = more causally load-bearing in the cascade."""
    candidate_nodes = [n for n in candidate_nodes if n in graph.nodes][:MAX_CANDIDATES]
    if not candidate_nodes:
        return {}

    baseline_spread = independent_cascade_spread(graph, candidate_nodes, propagation_prob, trials, rng_seed=seed)

    scores = {}
    for node in candidate_nodes:
        reduced_graph = graph.copy()
        reduced_graph.remove_node(node)
        reduced_seeds = [n for n in candidate_nodes if n != node]

        if not reduced_seeds:
            # This node was the only seed — its removal collapses the cascade entirely.
            scores[node] = round(baseline_spread, 4)
            continue

        spread_without = independent_cascade_spread(
            reduced_graph, reduced_seeds, propagation_prob, trials, rng_seed=seed
        )
        scores[node] = round(baseline_spread - spread_without, 4)

    return scores


def persist_causal_impact_scores(db: Session, scores: dict[str, float], run_id: str) -> None:
    for node_handle, score in scores.items():
        db.add(NodeInfluenceScore(node_handle=node_handle, algorithm_run_id=run_id, causal_impact_score=score))
    db.commit()

    append_block(db, "CAUSAL_IMPACT_RUN", {
        "run_id": run_id,
        "node_count": len(scores),
    })
