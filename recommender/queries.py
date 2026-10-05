import sqlite3
from datetime import timedelta

from recommender.config import AS_OF_DATE, DB_PATH, RECOMMENDABLE_ACCESS

def get_connection():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def get_user(conn, user_id):
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None

def get_user_topic_ids(conn, user_id):
    rows = conn.execute("SELECT topic_id FROM user_topic_interests WHERE user_id = ?", (user_id,))
    return {r["topic_id"] for r in rows}

def get_circle_tag_ids(conn):
    tags = {}
    for r in conn.execute("SELECT circle_id, topic_id FROM circle_tags"):
        tags.setdefault(r["circle_id"], set()).add(r["topic_id"])
    return tags

CANDIDATE_CIRCLES_SQL = """
    SELECT c.*,
           t.label AS topic_label,
           (SELECT COUNT(*) FROM memberships m
             WHERE m.circle_id = c.id AND m.role = 'leader') AS leader_count,
             COALESCE(SUM(a.reaction_count + a.comment_count + a.save_count), 0) AS engagement_30d
    FROM circles c
    LEFT JOIN topics t ON t.id = c.topic_id
    LEFT JOIN activity a ON a.circle_id = c.id AND a.created_at >= :cutoff
    WHERE c.access IN ({access_placeholders})
        AND (c.max_members IS NULL OR c.member_count < c.max_members)
        AND c.id NOT IN (SELECT circle_id FROM memberships WHERE user_id = :user_id)
    GROUP BY c.id
"""

def get_candidate_circles(conn, user_id):
    cutoff = (AS_OF_DATE - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    access_params = {f"access_{i}": a for i, a in enumerate(RECOMMENDABLE_ACCESS)}
    sql = CANDIDATE_CIRCLES_SQL.format(access_placeholders=", ".join(f":{name}" for name in access_params))
    
    tags= get_circle_tag_ids(conn)
    circles = []
    for r in conn.execute(sql, ({"cutoff": cutoff, "user_id": user_id, **access_params})):
        circle = dict(r)
        circle["tag_topic_ids"] = tags.get(circle["id"], set())
        circles.append(circle)
    return circles