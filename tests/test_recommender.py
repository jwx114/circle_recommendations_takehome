from datetime import datetime, timezone

import pytest

from recommender import queries, recommend, scoring
from recommender.__main__ import main
from recommender.ranking import limit_per_topic

AS_OF = datetime(2026, 9, 21, tzinfo=timezone.utc)


def top_ids(user_id, k=5):
    return [r["circle_id"] for r in recommend(user_id, k=k)]


def circle(**overrides):
    """A healthy, open, uncapped circle about topic 5. Override any field per test."""
    base = {
        "id": 1, "topic_id": 5, "tag_topic_ids": set(),
        "join_policy": "open", "max_members": None, "member_count": 10,
        "feed_posts_30d": 12, "chat_messages_30d": 150, "engagement_30d": 200,
        "last_activity_at": "2026-09-20 00:00:00+00:00",
    }
    return {**base, **overrides}


# ---------- Scenarios (planted records from the dataset README) ----------

def test_cold_start_returns_popular_circles_without_topic_claims():
    results = recommend(42)
    assert len(results) == 5
    for r in results:
        assert not any("interest" in reason for reason in r["reasons"])


def test_obvious_matches_rank_in_top_3():
    assert {5, 6} <= set(top_ids(7)[:3])


def test_duplicate_circles_are_not_all_returned():
    negotiation = {10, 11, 12} & set(top_ids(15))
    assert 1 <= len(negotiation) <= 2


def test_full_and_inactive_circles_do_not_rank():
    top = top_ids(23)
    assert top[0] == 22
    assert 20 not in top
    assert 21 not in top


# ---------- recommend() ----------

def test_recommend_k_limits_results():
    assert len(recommend(7, k=3)) == 3


@pytest.mark.parametrize("k", [0, -1])
def test_recommend_rejects_k_below_1(k):
    with pytest.raises(ValueError):
        recommend(7, k=k)


def test_recommend_k_larger_than_candidates_returns_each_circle_once():
    ids = top_ids(7, k=1000)
    assert len(ids) < 1000
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("user_id", [9999, 0, -1, None])
def test_recommend_unknown_user_raises(user_id):
    with pytest.raises(ValueError):
        recommend(user_id)


def test_recommend_never_returns_circles_the_user_already_joined():
    conn = queries.get_connection()
    try:
        joined = {r["circle_id"] for r in conn.execute("SELECT circle_id FROM memberships WHERE user_id = 7")}
    finally:
        conn.close()
    assert joined
    assert not joined & set(top_ids(7, k=1000))


# ---------- limit_per_topic() ----------

def ranked(*topic_ids):
    return [{"circle": {"id": i, "topic_id": t}} for i, t in enumerate(topic_ids, start=1)]


def test_limit_per_topic_caps_each_topic():
    picked = limit_per_topic(ranked(4, 4, 4, 9), k=5, max_per_topic=2)
    assert [p["circle"]["id"] for p in picked] == [1, 2, 4]


def test_limit_per_topic_never_caps_untagged_circles():
    assert len(limit_per_topic(ranked(None, None, None), k=5, max_per_topic=2)) == 3


def test_limit_per_topic_empty_input():
    assert limit_per_topic([], k=5) == []


@pytest.mark.parametrize("k", [0, -1])
def test_limit_per_topic_k_below_1_returns_nothing(k):
    assert limit_per_topic(ranked(1, 2, 3), k=k) == []


# ---------- topic_score() ----------

def test_topic_score_primary_match():
    assert scoring.topic_score(circle(), {5}) == 1.0


def test_topic_score_tag_only_match():
    assert scoring.topic_score(circle(topic_id=9, tag_topic_ids={5}), {5}) == 0.5


def test_topic_score_primary_and_tag_match_does_not_stack():
    assert scoring.topic_score(circle(tag_topic_ids={5, 7}), {5, 7}) == 1.0


def test_topic_score_no_overlap():
    assert scoring.topic_score(circle(topic_id=9, tag_topic_ids={3}), {5}) == 0.0


def test_topic_score_untagged_circle():
    assert scoring.topic_score(circle(topic_id=None), {5}) == 0.0


def test_topic_score_cold_start_user():
    assert scoring.topic_score(circle(), set()) == 0.0


def test_topic_score_missing_tags_fails_loudly():
    bad = circle()
    del bad["tag_topic_ids"]
    with pytest.raises(KeyError):
        scoring.topic_score(bad, {9})


# ---------- activity_score() ----------

def test_activity_score_at_targets_is_1():
    assert scoring.activity_score(circle()) == 1.0


def test_activity_score_caps_above_targets():
    assert scoring.activity_score(circle(feed_posts_30d=99, chat_messages_30d=999, engagement_30d=999)) == 1.0


def test_activity_score_half_of_targets():
    assert scoring.activity_score(circle(feed_posts_30d=6, chat_messages_30d=75, engagement_30d=100)) == pytest.approx(0.5)


def test_activity_score_no_activity_is_0():
    assert scoring.activity_score(circle(feed_posts_30d=0, chat_messages_30d=0, engagement_30d=0)) == 0.0


def test_activity_score_missing_field_fails_loudly():
    bad = circle()
    del bad["engagement_30d"]
    with pytest.raises(KeyError):
        scoring.activity_score(bad)


# ---------- fit_score() ----------

def test_fit_score_open_and_uncapped():
    assert scoring.fit_score(circle()) == 1.0


def test_fit_score_request_and_uncapped():
    assert scoring.fit_score(circle(join_policy="request")) == pytest.approx(0.8)


def test_fit_score_half_full():
    assert scoring.fit_score(circle(max_members=10, member_count=5)) == pytest.approx(0.75)


def test_fit_score_at_capacity_has_no_room():
    # Full circles are filtered in SQL; this documents what the function itself does
    assert scoring.fit_score(circle(max_members=10, member_count=10)) == pytest.approx(0.5)


def test_fit_score_unknown_join_policy_fails_loudly():
    with pytest.raises(KeyError):
        scoring.fit_score(circle(join_policy="invite_only"))


# ---------- recency_multiplier() ----------

@pytest.mark.parametrize("last_activity, expected", [
    ("2026-09-11 00:00:00+00:00", 1.0),    # 10 days: inside grace
    ("2026-09-07 00:00:00+00:00", 1.0),    # exactly 14 days: grace boundary
    ("2026-08-08 00:00:00+00:00", 0.5),    # 44 days: one half-life past grace
    ("2026-07-09 00:00:00+00:00", 0.25),   # 74 days: two half-lives
])
def test_recency_multiplier(last_activity, expected):
    assert scoring.recency_multiplier(circle(last_activity_at=last_activity), AS_OF) == pytest.approx(expected)


def test_recency_future_timestamp_is_not_a_bonus():
    assert scoring.recency_multiplier(circle(last_activity_at="2026-10-01 00:00:00+00:00"), AS_OF) == 1.0


@pytest.mark.parametrize("bad_value, error", [
    ("2026-09-07 00:00:00", TypeError),    # no timezone
    ("last tuesday", ValueError),          # not a timestamp
    (None, TypeError),                     # missing
])
def test_recency_bad_timestamp_fails_loudly(bad_value, error):
    with pytest.raises(error):
        scoring.recency_multiplier(circle(last_activity_at=bad_value), AS_OF)


# ---------- score_circle() ----------

def test_score_circle_perfect_circle_scores_1():
    assert scoring.score_circle(circle(), {5}, AS_OF)["score"] == pytest.approx(1.0)


def test_score_circle_returns_breakdown():
    result = scoring.score_circle(circle(), {5}, AS_OF)
    assert set(result) == {"circle", "score", "parts", "recency"}
    assert set(result["parts"]) == {"topic", "activity", "fit"}


def test_score_circle_cold_start_caps_at_activity_plus_fit():
    assert scoring.score_circle(circle(), set(), AS_OF)["score"] == pytest.approx(0.5)


def test_dead_circle_scores_below_unrelated_active_circle():
    dead = circle(feed_posts_30d=0, chat_messages_30d=0, engagement_30d=0,
                  last_activity_at="2026-02-01 00:00:00+00:00")
    active = circle(topic_id=9)
    assert scoring.score_circle(dead, {5}, AS_OF)["score"] < scoring.score_circle(active, {5}, AS_OF)["score"]


# ---------- CLI (__main__.py) ----------

def test_cli_success_exit_code(capsys):
    assert main(["23"]) == 0
    assert "Level Up Collective" in capsys.readouterr().out


def test_cli_unknown_user_exit_code_1(capsys):
    assert main(["9999"]) == 1
    assert "Unknown user_id" in capsys.readouterr().err


@pytest.mark.parametrize("argv", [["7", "-k", "0"], ["7", "-k", "-3"], ["abc"], []])
def test_cli_bad_arguments_exit_code_2(argv):
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 2
