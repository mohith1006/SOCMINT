"""
Propagation Replay (Section 7-E): time-ordered reconstruction of a topic's
spread across communities, exposed via API for frontend animation.

Reuses the topic associations that app/ml/pipeline.py already writes to
`post_topics` during NLP processing (step 7), and the most recent
persisted Louvain community assignment from app/analytics/network.py
(step 6) — this module is purely a read/reshape over data the other two
steps already produced, not a new classifier.
"""
from sqlalchemy.orm import Session

from app.models import Post, PostTopic, Community, UserCommunityMembership, SentimentScore


def get_propagation_replay(db: Session, topic_id: str) -> dict:
    posts_with_topic = (
        db.query(Post, PostTopic.score, SentimentScore.sentiment, SentimentScore.emotion_bucket)
        .join(PostTopic, PostTopic.post_id == Post.id)
        .outerjoin(SentimentScore, SentimentScore.post_id == Post.id)
        .filter(PostTopic.topic_id == topic_id)
        .filter(Post.posted_at.isnot(None))
        .order_by(Post.posted_at.asc())
        .all()
    )

    # Most recent persisted community run, same lookup pattern as
    # app/analytics/network.py's get_graph_payload.
    latest_community = db.query(Community).order_by(Community.created_at.desc()).first()
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

    frames = []
    communities_reached: set[str] = set()
    accounts_reached: set[str] = set()  # "reach" per the spec -- cumulative unique accounts, not just posts
    for post, match_score, sentiment, emotion_bucket in posts_with_topic:
        community_label = community_by_user.get(post.author_handle, "unassigned")
        communities_reached.add(community_label)
        accounts_reached.add(post.author_handle)
        frames.append({
            "timestamp": post.posted_at.isoformat(),
            "node": post.author_handle,
            "platform": post.platform,
            "community": community_label,
            "topic_match_score": round(match_score, 3),
            # sentiment/emotion_bucket are None if this post hasn't been through the
            # NLP pipeline yet (app/ml/pipeline.py) -- not "neutral", genuinely unknown.
            "sentiment": sentiment,
            "emotion_bucket": emotion_bucket,
            "cumulative_reach": len(accounts_reached),
            "cumulative_communities_reached": len(communities_reached),
        })

    mode = "computed" if frames else "static_sample"
    return {"mode": mode, "topic_id": topic_id, "frames": frames}
