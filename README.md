# Circle Recommendations

Recommends Circles for a user to join, based on the user's topic interests, Circle activity, and how easy the Circle is to join.

## Setup

Requires Python 3.11+. All commands run from the repo root (the folder containing this README).

```
pip install -r requirements.txt
python db/loader.py            # builds lean_in_mock.db from db/data/*.json
```

## Usage

```
python -m recommender 23           # top 5 for user 23
python -m recommender 15 -k 3      # top 3 for user 15
python -m recommender 42 --json    # JSON output for user 42
python -m recommender --help       # all options
pytest                             # scenario tests
```

An unknown user id prints `Error: Unknown user_id: <id>` and exits with code 1.

Example (`python -m recommender 23`):

```
Top 5 circles for user 23:

1. Level Up Collective (#22, Getting promoted) score 0.816
 Matches your interest in Getting promoted, Very active circle
2. Working Mothers United (#19, Working motherhood) score 0.626
 Related to your interests, Active circle
3. Mentors & Sponsors (#16, Sponsorship & mentorship) score 0.534
 Related to your interests, Open to join
4. Next Chapter Circle (#2, Career breaks) score 0.526
 Related to your interests, Open to join
5. Negotiation Circle (#10, Negotiation) score 0.492
 Very active circle, Open to join
```

The reasons under each Circle are the text a user would see, which is why they address the user directly.

Example (`python -m recommender 42 --json -k 2`, formatted for readability):

```json
[
  {
    "circle_id": 10,
    "name": "Negotiation Circle",
    "topic": "Negotiation",
    "score": 0.492,
    "reasons": ["Very active circle", "Open to join"]
  },
  {
    "circle_id": 1,
    "name": "The Elevation Circle",
    "topic": "Leadership skills",
    "score": 0.476,
    "reasons": ["Very active circle", "Open to join"]
  }
]
```

## How ranking works

`recommend(user_id, k)` in `recommender/ranking.py` runs four steps:

1. **Eligibility (SQL, `queries.py`).** Only Circles the user can actually join come back: public, not full, and not already joined.
2. **Scoring (Python, `scoring.py`).** Each eligible Circle gets a topic, activity, and fit score, multiplied by a recency penalty.
3. **Diversity (Python, `ranking.py`).** Sort by score, then keep at most 2 Circles per primary topic until there are `k`.
4. **Explain.** Each result carries short reasons built from its score breakdown.

```
score = (0.5 * topic + 0.3 * activity + 0.2 * fit) * recency
```

- **Topic (0.5).** 1.0 if the Circle's primary topic is one of the user's interests, 0.5 if the interest only appears in the Circle's tags, 0 otherwise.
- **Activity (0.3).** Average of three capped ratios: posts, chat messages, and engagement (reactions + comments + saves) over the last 30 days.
- **Fit (0.2).** Average of join policy (open 1.0, request 0.6) and room left in the Circle (uncapped = 1.0).
- **Recency (multiplier).** No penalty for the first 14 days without activity, then the score halves every 30 days.

Full Circles are filtered out because they can't be joined. Inactive Circles are penalized instead of filtered, since inactivity is a matter of degree. A user with no interests (cold start) scores 0 on topic everywhere, so the ranking falls back to the most active, easiest-to-join Circles with no special code path.

All weights and thresholds live in `recommender/config.py`. See [DESIGN_DOC.md](DESIGN_DOC.md) for the schema and the reasoning behind each ranking decision.

## Scenario results

| Scenario | User | Top 5 | Result |
| --- | --- | --- | --- |
| Cold start | 42 | 10, 1, 31, 11, 3 | Most active, open Circles; no topic match claimed |
| Obvious matches | 7 | 1, 5, 6, 31, 38 | #5 Women Who Lead and #6 Speak Up Circle in the top 3 |
| Duplicate Circles | 15 | 10, 11, 13, 37, 1 | 2 of the 3 near-identical Negotiation Circles, then other topics |
| Full / inactive | 23 | 22, 19, 16, 2, 10 | #22 Level Up Collective first; #20 (full) and #21 (unlisted, inactive) excluded |

## Project layout

```
db/            schema.sql, loader.py (JSON -> SQLite), helpers.py, data/
recommender/   config.py      weights and thresholds
               queries.py     SQL + eligibility filters
               scoring.py     per-Circle scores
               ranking.py     sort, per-topic limit, explanations
               __main__.py    CLI
tests/         scenario tests
```

---

# Seed dataset — Recommend Circles to Join

This folder is the dataset for the take-home. It's a small, **fully synthetic** snapshot
of a Lean In Connect–style community: members, Circles, who belongs to which Circle,
the topic taxonomy, and recent Circle feed activity.

Everything here is generated (`generate.mjs`) — no real people, no real content.

## Files

| File | Rows | What it is |
| --- | --- | --- |
| `data/topics.json` | 22 | The topic taxonomy Circles and members are tagged with |
| `data/users.json` | 100 | Members: profile fields + stated topic interests |
| `data/circles.json` | 40 | Circles: profile, topic, capacity, and activity aggregates |
| `data/memberships.json` | ~440 | Who belongs to which Circle, and their role |
| `data/activity.json` | ~390 | Recent Circle feed posts with engagement counts |

## Loading it

The data is plain JSON so it drops into anything — Postgres, SQLite, or just an
in-memory array. Load it however suits your design; you don't have to mirror our shapes.

```js
const users = JSON.parse(fs.readFileSync("data/users.json", "utf8"));
```

## Data dictionary

### `topics.json`
| field | type | notes |
| --- | --- | --- |
| `id` | int | |
| `slug` | string | kebab-case, e.g. `negotiation` |
| `label` | string | display name |
| `domain` | string | always `content` here |

### `users.json`
| field | type | notes |
| --- | --- | --- |
| `id` | int | |
| `first_name`, `last_name` | string | synthetic |
| `has_photo` | bool | whether a profile photo is set |
| `bio` | string \| null | |
| `job_title` | string \| null | |
| `company` | string \| null | |
| `industry` | string \| null | |
| `location` | string \| null | |
| `joined_at` | ISO datetime | account age / tenure signal |
| `topic_interests` | string[] | topic slugs the member selected; **may be empty** |
| `profile_completeness` | number 0–1 | share of {photo, bio, job title, company-or-industry, location} present |

### `circles.json`
| field | type | notes |
| --- | --- | --- |
| `id` | int | |
| `name`, `slug`, `description` | string / null | `description` and `cover_image_url` may be null |
| `topic` | string \| null | topic slug; **some Circles have no topic** |
| `tags` | string[] | free-form topic-ish tags |
| `cover_image_url` | string \| null | |
| `format` | enum | `in_person` \| `virtual` \| `hybrid` |
| `access` | enum | `public` \| `unlisted` |
| `join_policy` | enum | `open` \| `request` |
| `max_members` | int \| null | capacity; **null means uncapped** |
| `member_count` | int | current members |
| `created_at` | ISO datetime | |
| `last_activity_at` | ISO datetime | timestamp of the most recent activity |
| `feed_posts_30d` | int | posts in the last 30 days |
| `chat_messages_30d` | int | group-chat message volume in the last 30 days (aggregate count only) |

### `memberships.json`
| field | type | notes |
| --- | --- | --- |
| `user_id` | int | → `users.id` |
| `circle_id` | int | → `circles.id` |
| `role` | enum | `member` \| `leader` (a Circle's leaders are just members with `role=leader`) |
| `joined_at` | ISO datetime | |

### `activity.json`
| field | type | notes |
| --- | --- | --- |
| `id` | int | |
| `circle_id` | int | → `circles.id` |
| `author_user_id` | int | → `users.id` (always a member of that Circle) |
| `body` | string | post text |
| `reaction_count`, `comment_count`, `save_count` | int | engagement on the post |
| `created_at` | ISO datetime | |

## A few things are intentionally *derived*, not stored

Mirroring the real product, some signals aren't handed to you as a column — you decide
how to compute them:

- **Is a Circle full?** Compare `member_count` to `max_members` (and `max_members` can be null).
- **How active is a Circle?** Combine `feed_posts_30d`, `last_activity_at`, `chat_messages_30d`,
  and engagement in `activity.json` however you think best.
- **A Circle's leaders and their profiles** come from `memberships` (`role=leader`) joined to `users`.

## What we deliberately did *not* include

- **Embeddings / precomputed similarity.** Topic overlap and the fields above are enough for this exercise.
- **Raw group-chat message text.** Only the aggregate `chat_messages_30d` count, for privacy realism.

## Named records for the scenarios

The assignment says we'll run your submission against planted records. Here they are —
build so these return sensible results, and be ready to talk through them:

| Scenario | Run for | What's planted |
| --- | --- | --- |
| **Cold start** | `user_id 42` | No memberships, no stated interests, empty profile (`profile_completeness = 0`) |
| **Obvious matches** | `user_id 7` | Interests `leadership-skills`, `public-speaking`; strong active/open Circles exist for both (`#5 Women Who Lead`, `#6 Speak Up Circle`) that she hasn't joined |
| **Duplicate Circles** | `user_id 15` | Interest `negotiation`; Circles `#10`, `#11`, `#12` are three near-identical active Negotiation Circles — a good list shouldn't return all three |
| **Full / inactive** | `user_id 23` | Interest `getting-promoted`; `#20 The Promotion Path` is **full** (at capacity) and `#21 Career Climbers` is **inactive** (no posts in ~7 months) — both look like great topic matches but shouldn't rank; `#22 Level Up Collective` is the healthy alternative |

Regenerate the data anytime with `node generate.mjs` (it's deterministic — same output every run).
