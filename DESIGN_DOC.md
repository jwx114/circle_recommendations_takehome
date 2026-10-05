# Database Schema

## Tables

**Core entities (4):**
- `topics(id, slug, label, domain)`: the content taxonomy.
- `users(id, first_name, last_name, has_photo, bio, job_title, company, industry, location, joined_at, profile_completeness)`
- `circles(id, name, slug, description, topic_id, cover_image_url, format, access, join_policy, max_members, member_count, created_at, last_activity_at, feed_posts_30d, chat_messages_30d)`: `topic_id` is a nullable FK to `topics`.
- `activity(id, circle_id, author_user_id, body, reaction_count, comment_count, save_count, created_at)`

**Join tables (3):**
- `memberships(user_id, circle_id, role, joined_at)`: composite PK `(user_id, circle_id)`.
- `circle_tags(circle_id, topic_id)`: composite PK `(circle_id, topic_id)`.
- `user_topic_interests(user_id, topic_id)`: composite PK `(user_id, topic_id)`.

## Relationships

- **Circle → Activity ← Users**: two one-to-many FKs (`activity.circle_id`, `activity.author_user_id`). Activity is its own entity with its own primary key, not a junction table.
- **Circle ↔ Users via `memberships`**: many-to-many, and a "rich" junction: it carries `role` and `joined_at`, not just the two foreign keys.
- **Topic → Circle** (primary topic): one-to-many via `circles.topic_id`, nullable.
- **Circle ↔ Topic via `circle_tags`**: many-to-many, a pure junction (no attributes beyond the two FKs).
- **User ↔ Topic via `user_topic_interests`**: many-to-many, also a pure junction.

## Key design decisions

**SQLite over Postgres.** At this dataset's size (~40 circles, ~100 users, ~440 memberships), engine choice has no measurable performance effect. SQLite wins purely on operational simplicity: no server for a grader to install or configure to run this locally. The real tradeoff is SQLite's single-writer model, which would become a genuine constraint under concurrent production write load (many simultaneous joins/posts): that's the first thing to change moving toward production scale.

**Normalized `tags` and `topic_interests` into real join tables rather than keeping them as inline arrays.** The raw seed data stores both as JSON arrays. Denormalizing them into the schema as-is would push topic-overlap computation into application code as array intersection; normalizing into `circle_tags`/`user_topic_interests` makes topic matching a SQL join instead, which is simpler and the only approach that scales past this dataset's size.

**`circles.topic` kept as its own scalar FK, not folded into `circle_tags`.** A circle's primary topic and its tags are semantically distinct: exactly one (or none) primary topic vs. zero-to-many tags, and the primary topic is the single most heavily queried signal in the ranking logic. A scalar column keeps that lookup a plain equality check rather than a filtered join, and gets "at most one primary topic" enforced for free by the column itself. The alternative (one unified many-to-many table with an `is_primary` flag) is more textbook-normalized, but needs a partial unique index to get the same guarantee, for no query-time benefit given how dominant this one lookup is.

**`circles.topic_id` is nullable, confirmed against the actual seed data, not assumed.** Two circles have no primary topic and no tags at all: apparent identity/geography-based circles that fall outside the content taxonomy entirely. Both the schema and the ranking logic need to tolerate this rather than assuming every circle is topically classified.

**`memberships` is a "rich" junction; `circle_tags`/`user_topic_interests` are "pure" junctions.** This reflects a real difference, not an inconsistency: membership genuinely carries its own data (when the user joined, what role the user holds), while a tag or a stated interest is just a link with nothing further attached to it.

## Indexing

- The composite primary keys on all three join tables double as the index needed for their most common access pattern: "every topic for circle X," "every circle user Y belongs to."
- `circles.last_activity_at`: worth its own index, since the ranking logic filters/penalizes on recency for every recommendation request; this is a hot-path `WHERE` column, not just bookkeeping.
- `circles.topic_id`: same reasoning; it's the anchor of the dominant scoring signal and gets touched on essentially every request.

# Ranking

`recommend(user_id, k)` in `recommender/ranking.py` runs four steps:

1. **Eligibility (SQL, `queries.py`).** Only circles the user can actually join come back: public, not full, and not already joined.
2. **Scoring (Python, `scoring.py`).** Each eligible circle gets a topic, activity, and fit score, multiplied by a recency penalty.
3. **Diversity (Python, `ranking.py`).** Sort by score, then keep at most 2 circles per primary topic until there are `k`.
4. **Explain.** Each result carries short reasons built from its score breakdown ("Matches your interest in Negotiation", "Very active circle", "Open to join").

## Score

```
score = (0.5 * topic + 0.3 * activity + 0.2 * fit) * recency
```

- **Topic (0.5).** 1.0 if the circle's primary topic is one of the user's interests, 0.5 if the interest only appears in the circle's tags, 0 otherwise. The best match wins; matches don't stack, so the score never goes above 1.0.
- **Activity (0.3).** The average of three capped ratios: `feed_posts_30d / 12`, `chat_messages_30d / 150`, and `engagement_30d / 200`, where engagement is reactions + comments + saves on posts from the last 30 days, computed from `activity`. Each ratio caps at 1.0.
- **Fit (0.2).** How easy the circle is to join: the average of join policy (open 1.0, request 0.6) and room left (`1 - member_count / max_members`, uncapped = 1.0).
- **Recency (multiplier).** No penalty for the first 14 days without activity, then the score halves every 30 days.

All weights and thresholds live in `recommender/config.py`.

## Key ranking decisions

**Filter full, penalize inactive.** Full is a yes/no fact: a full circle can't be joined, so recommending it is a dead end and it's removed in SQL. Inactivity is a matter of degree (quiet for 3 weeks vs. dead for 7 months), so it lowers the score instead of removing the circle. Unlisted circles are also filtered, since they aren't meant to be discovered.

**Eligibility filters in SQL, scoring and sorting in Python.** Filtering in the database means circles that would be thrown away are never loaded, and the filter guarantees the scoring assumptions (for example, `member_count / max_members` is always below 1 and `max_members` is never 0). Scoring stays in Python because it combines several signals, needs `0.5 ** x` (not available in every SQLite build), and the per-topic limit depends on what's already been picked, which an `ORDER BY` can't express. Every scoring function is pure, so it can be tested without a database.

**Recency is a multiplier, not a weighted term.** As a weighted term, a dead circle with a perfect topic match would still keep the 0.5 from topic. As a multiplier, everything scales down: #32 The Resilience Room (235 days quiet) would score 0.2 on fit alone, but scores about 0.001 with the penalty and ranks last for every user. The 14 grace days keep circles that meet every couple of weeks from being penalized (#40 Network & Grow, 20 days quiet, keeps about 87%).

**Fixed activity targets instead of dividing by the busiest circle.** Dividing by the max lets one outlier pull every other circle's score down and makes scores shift whenever the data changes. The targets sit a bit above the median (posts 6, chat 38, engagement 41) so a healthy circle reaches 1.0, and the cap means a louder circle doesn't beat a better topic match.

**At most 2 circles per primary topic, confirmed against the scenarios, not assumed.** With a limit of 1, user 7 loses #5 Women Who Lead because #1 The Elevation Circle has the same primary topic. With 2, user 7 gets #5 and #6, and user 15 gets 2 of the 3 near-identical Negotiation circles instead of all three. Circles with no topic are never limited, since two untagged circles aren't duplicates of each other.

**Cold start falls out of the scoring.** A user with no interests scores 0 on topic for every circle, so ranking comes down to activity and fit: the most active, easiest-to-join circles. There is no special code path, and the reasons never claim a topic match the user didn't make.

**`AS_OF_DATE` is pinned to 2026-09-21.** The seed data is generated relative to that date (`generate.mjs`), and `feed_posts_30d` is already measured from it. Using `now()` would make every circle look weeks staler than the data intends. In production this would be `now()`.

**No leader signal.** Every circle in the seed data has exactly one leader, so a leader-based score would be the same for every circle and add nothing.

**Stored aggregates checked against raw data.** `feed_posts_30d` matches the count of posts in `activity` for every circle, so the stored column is used and the duplicate count was dropped.

## Scenario results

| Scenario | User | Top 5 | Result |
| --- | --- | --- | --- |
| Cold start | 42 | 10, 1, 31, 11, 3 | Most active, open circles |
| Obvious matches | 7 | 1, 5, 6, 31, 38 | #5 and #6 in the top 3 |
| Duplicate circles | 15 | 10, 11, 13, 37, 1 | 2 of the 3 Negotiation circles |
| Full / inactive | 23 | 22, 19, 16, 2, 10 | #22 first; #20 (full) and #21 (unlisted, inactive) excluded |

## Next steps

- **Tune weights with real data.** The weights and targets are reasonable defaults; real join and retention data would show what actually predicts a good match for users.
- **Topic similarity.** Today topic match is exact. Co-occurrence or embeddings would let related topics (negotiation and getting promoted) partially match.
- **Better duplicate detection.** Duplicates are detected by primary topic only. Comparing tags or names would catch near-duplicates with different topics.
- **API layer.** `recommend()` already returns plain dicts, so `GET /users/{id}/recommendations` is a thin wrapper.
- **Safer loader.** `executescript` commits the drops right away, so a failed load leaves empty tables. Building into a temp file and swapping it in after the FK check passes would fix that.
- **Scale.** At larger sizes, move scoring into SQL or precompute scores, and filter on recency in the query.
