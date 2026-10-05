from datetime import datetime

from recommender.config import AS_OF_DATE, INACTIVITY_GRACE_DAYS, INACTIVITY_HALF_LIFE_DAYS, JOIN_POLICY_FIT, PRIMARY_TOPIC_MATCH, TAG_MATCH, ACTIVITY_TARGETS, WEIGHTS, WEIGHTS

def topic_score(circle, user_topic_ids):
    if circle["topic_id"] in user_topic_ids:
        return PRIMARY_TOPIC_MATCH
    if circle["tag_topic_ids"] & user_topic_ids:
        return TAG_MATCH
    return 0.0

def activity_score(circle):
    parts = [min(circle[field] / target, 1.0) for field, target in ACTIVITY_TARGETS.items()]
    activity_score = sum(parts) / len(parts) if parts else 0.0
    return activity_score

def fit_score(circle):
    policy = JOIN_POLICY_FIT[circle["join_policy"]]
    if circle["max_members"] is None:
        room = 1.0
    else:
        room = 1 - (circle["member_count"] / circle["max_members"])
    fit_score = (policy + room) / 2.0
    return fit_score


def recency_multiplier(circle, as_of=AS_OF_DATE):
    last_activity = datetime.fromisoformat(circle["last_activity_at"])
    days_since = (as_of - last_activity).total_seconds() / 86400  # Convert to days
    days_quiet = max(0.0, days_since - INACTIVITY_GRACE_DAYS)
    recency = .5 ** (days_quiet / INACTIVITY_HALF_LIFE_DAYS)
    return recency

def score_circle(circle, user_topic_ids, as_of=AS_OF_DATE):
    parts = {
        "topic": topic_score(circle, user_topic_ids),
        "activity": activity_score(circle),
        "fit": fit_score(circle),
    }
    base = sum(WEIGHTS[name] * value for name, value in parts.items())
    recency = recency_multiplier(circle, as_of)
    return {"circle": circle, "score": base * recency, "parts": parts, "recency": recency}