"""
Synthetic data generator — makes the full demo path (dashboard, sentiment,
trends, network, demographics) work end-to-end with zero live API keys, for
reliability during judging.

Run: python -m scripts.generate_synthetic_data

Rewritten from the original version, which assigned every post author and
every interaction pair via pure `random.choice`/`random.sample` — uniform
random data has no real community structure for Louvain to find and no
real hub/bridge accounts for centrality to surface, so the network demo
page would show an undifferentiated blob rather than anything resembling
what real interaction data looks like. It also created `Topic` rows with
no `PostTopic` links, so Propagation Replay came back empty until someone
separately ran `/nlp/process` against synthetic text that may or may not
have matched those exact topic labels.

This version embeds structure on purpose:
  - 5 thematic communities (matching SAMPLE_TOPICS), each with a couple of
    hub accounts (deliberately over-targeted) — real clusters and real
    high-in-degree accounts for Louvain/centrality to actually recover.
  - One designated bridge account per community pair, interacting across
    both communities more than chance — a real structural bridge for
    betweenness centrality to find.
  - Sentiment/emotion/topic data is generated directly (not requiring a
    separate `/nlp/process` run first) so Sentiment Timeline, Trends, and
    Propagation Replay all have real data immediately after this script
    runs — the whole point of a judging-reliability fallback dataset is
    that every page works right away, not after several more manual steps.
"""
import random
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal, Base, engine
from app.models import Post, Interaction, Topic, PostTopic, SentimentScore

COMMUNITY_THEMES = {
    "monsoon_relief": {
        "topic_label": "monsoon relief",
        "sentences": [
            "Relief camps are running low on supplies in the flooded districts.",
            "Volunteers have been incredible helping families displaced by the flooding.",
            "Frustrated with how slow the relief funds are reaching affected villages.",
            "The monsoon this year has been far worse than officials predicted.",
        ],
    },
    "budget_session": {
        "topic_label": "budget session",
        "sentences": [
            "The new budget announcement is getting a lot of attention today.",
            "Excited about the infrastructure spending outlined in this year's budget.",
            "Concerned the budget session didn't address rural healthcare at all.",
            "Opposition is calling the budget session a missed opportunity.",
        ],
    },
    "cricket_world_cup": {
        "topic_label": "cricket world cup",
        "sentences": [
            "That cricket match last night was absolutely incredible.",
            "Can't believe we lost the world cup match in the final over.",
            "The whole neighborhood was celebrating after that world cup win.",
            "This world cup squad selection has fans arguing all week.",
        ],
    },
    "startup_funding": {
        "topic_label": "startup funding",
        "sentences": [
            "Startup ecosystem here keeps growing every quarter.",
            "Another funding round announced for a homegrown startup today.",
            "Worried this startup funding boom is more hype than substance.",
            "Great to see more startup funding going toward rural fintech.",
        ],
    },
    "metro_expansion": {
        "topic_label": "metro expansion",
        "sentences": [
            "Traffic near the metro construction site has been terrible all week.",
            "The new metro expansion line is finally opening next month.",
            "Metro expansion is years behind schedule at this point.",
            "Commute time cut in half since the metro expansion reached our area.",
        ],
    },
}

SAMPLE_LANGS = ["en", "hi", "ta", "bn", "te"]
SAMPLE_PLATFORMS = ["telegram", "reddit", "x"]
SENTIMENTS = ["positive", "negative", "neutral"]


def generate(num_posts_per_community: int = 60, seed: int = 42):
    rng = random.Random(seed)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        community_names = list(COMMUNITY_THEMES.keys())

        # 8 members per community, 2 of them designated hubs (over-targeted by interactions).
        handles_by_community: dict[str, list[str]] = {}
        hubs_by_community: dict[str, list[str]] = {}
        for community in community_names:
            members = [f"{community}_user_{i}" for i in range(8)]
            handles_by_community[community] = members
            hubs_by_community[community] = members[:2]

        # One bridge account per adjacent community pair, present in both member lists.
        bridge_pairs = list(zip(community_names, community_names[1:] + community_names[:1]))
        bridges: dict[tuple[str, str], str] = {}
        for c1, c2 in bridge_pairs:
            bridge_handle = f"bridge_{c1}_{c2}"
            handles_by_community[c1].append(bridge_handle)
            handles_by_community[c2].append(bridge_handle)
            bridges[(c1, c2)] = bridge_handle

        topics_by_community: dict[str, Topic] = {}
        for community, theme in COMMUNITY_THEMES.items():
            topic = Topic(
                label=theme["topic_label"],
                first_seen=datetime.now(timezone.utc) - timedelta(days=7),
                velocity_score=round(rng.uniform(0.5, 4.0), 2),
            )
            db.add(topic)
            topics_by_community[community] = topic
        db.flush()  # populate topic.id for the PostTopic rows below

        total_posts = 0
        total_interactions = 0

        for community, theme in COMMUNITY_THEMES.items():
            members = handles_by_community[community]
            hubs = hubs_by_community[community]
            other_members = [m for c, ms in handles_by_community.items() if c != community for m in ms]

            for i in range(num_posts_per_community):
                author = rng.choice(members)
                posted_at = datetime.now(timezone.utc) - timedelta(hours=rng.uniform(0, 72))
                text = rng.choice(theme["sentences"])
                lang = rng.choices(SAMPLE_LANGS, weights=[0.5, 0.2, 0.1, 0.1, 0.1])[0]
                is_india_signal = rng.random() < 0.85  # a few unclassified for realism

                post = Post(
                    platform=rng.choice(SAMPLE_PLATFORMS),
                    platform_post_id=f"synthetic_{community}_{i}",
                    author_handle=author,
                    text=text,
                    lang=lang,
                    region_tag="india" if is_india_signal else "unclassified",
                    region_confidence=round(rng.uniform(0.4, 0.95), 2) if is_india_signal else round(rng.uniform(0.05, 0.3), 2),
                    posted_at=posted_at,
                    raw_metadata={"synthetic": True, "community_ground_truth": community},
                )
                db.add(post)
                db.flush()  # populate post.id for PostTopic/SentimentScore below
                total_posts += 1

                # Directly link this post to its community's topic -- skips needing
                # a separate /nlp/process run before Propagation Replay has data.
                db.add(PostTopic(post_id=post.id, topic_id=topics_by_community[community].id,
                                  score=round(rng.uniform(0.4, 0.95), 4)))

                sentiment = rng.choices(SENTIMENTS, weights=[0.4, 0.3, 0.3])[0]
                emotion_bucket = {
                    "positive": rng.choice(["happy", "joyful"]),
                    "negative": rng.choice(["sad", "angry", "low_mood_distress_signal"]),
                    "neutral": "happy",
                }[sentiment]
                stance = {"positive": "supportive", "negative": "against", "neutral": "neutral"}[sentiment]
                db.add(SentimentScore(
                    post_id=post.id,
                    sentiment=sentiment,
                    emotion_bucket=emotion_bucket,
                    stance_topic_id=topics_by_community[community].id,
                    stance=stance,
                    confidence=round(rng.uniform(0.55, 0.95), 4),
                    # Sarcasm is English-only by design (app/ml/sarcasm.py) -- None
                    # for other languages means "not evaluated", not "not sarcastic".
                    sarcasm_flag=(rng.random() < 0.08) if lang == "en" else None,
                    sarcasm_confidence=round(rng.uniform(0.5, 0.9), 4) if lang == "en" else None,
                ))

                # Interactions: mostly within-community, biased toward this
                # community's hub accounts; bridge accounts occasionally connect
                # across their two adjacent communities.
                if rng.random() < 0.7:
                    if author in bridges.values() and rng.random() < 0.5:
                        target = rng.choice(other_members)
                    elif rng.random() < 0.4:
                        target = rng.choice(hubs)
                    else:
                        target = rng.choice(members)
                    if target != author:
                        db.add(Interaction(
                            source_user=author,
                            target_user=target,
                            type=rng.choice(["mention", "reply", "share", "follow"]),
                            weight=round(rng.uniform(0.5, 1.0), 2),
                            timestamp=posted_at,
                        ))
                        total_interactions += 1

        db.commit()

        from app.blockchain.ledger import append_block
        append_block(db, "INGESTION_CHECKPOINT", {
            "platform": "synthetic",
            "post_count": total_posts,
            "interaction_count": total_interactions,
            "note": "Static/Sample Data — not live",
        })
        print(
            f"Generated {total_posts} synthetic posts, {total_interactions} interactions, "
            f"{len(COMMUNITY_THEMES)} topics (with sentiment + topic links pre-populated).\n"
            "Run POST /network/analyze next to detect communities from this data, then "
            "GET /network/graph, GET /trends, GET /sentiment/timeline, and "
            "GET /network/propagation-replay/{topic_id} should all show real results."
        )
    finally:
        db.close()


if __name__ == "__main__":
    generate()
