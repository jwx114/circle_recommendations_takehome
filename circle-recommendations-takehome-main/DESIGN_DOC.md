  # Database Schema

  ## Tables

  **Core entities (4):**
  - `topics(id, slug, label, domain)` — the content taxonomy.
  - `users(id, first_name, last_name, has_photo, bio, job_title, company, industry, location, joined_at,profile_completeness)`
  - `circles(id, name, slug, description, topic_id, cover_image_url, format, access, join_policy, max_members, member_count, created_at, last_activity_at, feed_posts_30d, chat_messages_30d)`: `topic_id` is a nullable FK to `topics`.
  - `activity(id, circle_id, author_user_id, body, reaction_count, comment_count, save_count, created_at)`
  
  **Join tables (3):**
  - `memberships(user_id, circle_id, role, joined_at)`: composite PK `(user_id, circle_id)`.
  - `circle_tags(circle_id, topic_id)`: composite PK `(circle_id, topic_id)`.
  - `user_topic_interests(user_id, topic_id)`: composite PK `(user_id, topic_id)`.

  ## Relationships

  - **Circle → Activity ← Users**: two one-to-many FKs (`activity.circle_id`, `activity.author_user_id`). Activity is its own entity with its own primary key, not a junction table.
  - **Circle ↔ Users via `memberships`**: many-to-many, and a "rich" junction — it carries `role` and `joined_at`, not just the two foreign keys.
  - **Topic → Circle** (primary topic): one-to-many via `circles.topic_id`, nullable.
  - **Circle ↔ Topic via `circle_tags`**: many-to-many, a pure junction (no attributes beyond the two FKs).
  - **User ↔ Topic via `user_topic_interests`**: many-to-many, also a pure junction.

  ## Key design decisions

  **SQLite over Postgres.** At this dataset's size (~40 circles, ~100 users, ~440 memberships), engine choice has no measurable performance effect — SQLite wins purely on operational simplicity: no server for a grader to install or configure to run this locally. The real tradeoff is SQLite's single-writer model, which would become a genuine constraint under concurrent production write load (many simultaneous joins/posts): that's the first thing to change moving toward production scale.

  **Normalized `tags` and `topic_interests` into real join tables rather than keeping them as inline arrays.** The raw seed data stores both as JSON arrays. Denormalizing them into the schema as-is would push topic-overlap computation into application code as array intersection; normalizing into `circle_tags`/`user_topic_interests` makes topic matching a SQL join instead — simpler, and the only approach that scales past this dataset's size.

  **`circles.topic` kept as its own scalar FK, not folded into `circle_tags`.** A circle's primary topic and its tags are semantically distinct — exactly one (or none) primary topic vs. zero-to-many tags and the primary topic is the single most heavily queried signal in the ranking logic. A scalar column keeps that lookup a plain equality check rather than a filtered join, and gets "at most one primary topic" enforced for free by the column itself. The alternative (one unified many-to-many table with an `is_primary` flag) is more textbook-normalized, but needs a partial unique index to get the same guarantee, for no query-time benefit given how dominant this one lookup is.

  **`circles.topic_id` is nullable — confirmed against the actual seed data, not assumed.** Two circles have no primary topic and no tags at all — apparent identity/geography-based circles that fall outside the content taxonomy entirely. Both the schema and the ranking logic need to tolerate this rather than assuming every circle is topically classified.

  **`memberships` is a "rich" junction; `circle_tags`/`user_topic_interests` are "pure" junctions.** This reflects a real difference, not an inconsistency: membership genuinely carries its own data (when you joined, what role you hold), while a tag or a stated interest is just a link with nothing further attached to it.

  ## Indexing

  - The composite primary keys on all three join tables double as the index needed for their most common access pattern: "every topic for circle X," "every circle user Y belongs to."
  - `circles.last_activity_at`: worth its own index, since the ranking logic filters/penalizes on recency for every recommendation request; this is a hot-path `WHERE` column, not just bookkeeping.
  - `circles.topic_id`: same reasoning; it's the anchor of the dominant scoring signal and gets touched on essentially every request.