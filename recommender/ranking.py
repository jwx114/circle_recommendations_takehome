from recommender import queries
from recommender.config import AS_OF_DATE, DEFAULT_K, MAX_PER_TOPIC, PRIMARY_TOPIC_MATCH, TAG_MATCH
from recommender.scoring import score_circle

def recommend(user_id, k=DEFAULT_K, as_of=AS_OF_DATE):
    conn = queries.get_connection()
    try:
        if queries.get_user(conn, user_id) is None:
            raise ValueError(f"Unknown user_id: {user_id}")
        user_topic_ids = queries.get_user_topic_ids(conn, user_id)
        candidates = queries.get_candidate_circles(conn, user_id)
    finally:
        conn.close()
    scored = [score_circle(circle, user_topic_ids, as_of) for circle in candidates]
    scored.sort(key=lambda r: (-r["score"], r["circle"]["id"]))
    top = limit_per_topic(scored, k)
    return [to_result(item) for item in top]

def limit_per_topic(scored, k, max_per_topic=MAX_PER_TOPIC):
    picked, per_topic = [], {}
    for item in scored:
        topic_id = item["circle"]["topic_id"]
        if topic_id is not None and per_topic.get(topic_id, 0) >= max_per_topic:
            continue
        per_topic[topic_id] = per_topic.get(topic_id, 0) + 1
        picked.append(item)
        if len(picked) == k:
            break
    return picked

def explain(item):
    circle, parts = item["circle"], item["parts"]
    reasons = []
    if parts["topic"] == PRIMARY_TOPIC_MATCH:
        reasons.append(f"Matches your interest in {circle['topic_label']}")
    elif parts["topic"] == TAG_MATCH:
        reasons.append("Related to your interests")
    if parts["activity"] >= 0.75:
        reasons.append("Very active circle")
    elif parts["activity"] >= 0.4:
        reasons.append("Active circle")
    if circle["join_policy"] == "open":
        reasons.append("Open to join")
    return reasons

def to_result(item):
    circle = item["circle"]
    return {
        "circle_id": circle["id"],
        "name": circle["name"],
        "topic": circle["topic_label"],
        "score": round(item["score"], 3),
        "reasons": explain(item),
    }