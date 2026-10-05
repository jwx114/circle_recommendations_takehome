DROP TABLE IF EXISTS topics;
CREATE TABLE topics (
    id INTEGER PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    label TEXT NOT NULL,
    domain TEXT
);

DROP TABLE IF EXISTS circles;
CREATE TABLE circles (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT, -- nullable
    cover_image_url TEXT,
    topic_id INTEGER REFERENCES topics(id), -- nullable
    format TEXT CHECK(format IN('in_person', 'virtual', 'hybrid' )),
    access TEXT CHECK(access IN('public', 'unlisted' )),
    join_policy TEXT CHECK(join_policy IN('open', 'request' )),
    max_members INTEGER, -- null == uncapped
    member_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT,
    last_activity_at TEXT,
    feed_posts_30d INTEGER NOT NULL DEFAULT 0,
    chat_messages_30d INTEGER NOT NULL DEFAULT 0
);

DROP TABLE IF EXISTS activity;
CREATE TABLE activity (
    id INTEGER PRIMARY KEY,
    author_user_id INTEGER NOT NULL REFERENCES users(id),
    circle_id INTEGER NOT NULL REFERENCES circles(id),
    body TEXT,
    reaction_count INTEGER NOT NULL DEFAULT 0,
    comment_count INTEGER NOT NULL DEFAULT 0,
    save_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT
);

DROP TABLE IF EXISTS memberships;
CREATE TABLE memberships (
    user_id INTEGER NOT NULL REFERENCES users(id),
    circle_id INTEGER NOT NULL REFERENCES circles(id),
    role TEXT NOT NULL CHECK(role IN('member', 'leader')),
    joined_at TEXT,
    PRIMARY KEY (user_id, circle_id)
);

DROP TABLE IF EXISTS circle_tags;
CREATE TABLE circle_tags (
    circle_id INTEGER,
    topic_id INTEGER,
    PRIMARY KEY (circle_id, topic_id),
    FOREIGN KEY (circle_id) REFERENCES circles(id),
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);

DROP TABLE IF EXISTS users;
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    has_photo INTEGER NOT NULL DEFAULT 0,
    bio TEXT,
    job_title TEXT,
    company TEXT,
    industry TEXT,
    location TEXT,
    joined_at TEXT,
    profile_completeness REAL NOT NULL DEFAULT 0
);

DROP TABLE IF EXISTS user_topic_interests;
CREATE TABLE user_topic_interests (
    user_id INTEGER,
    topic_id INTEGER,
    PRIMARY KEY (user_id, topic_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);

CREATE INDEX idx_circles_topic_id ON circles(topic_id);
CREATE INDEX idx_activity_circle_id ON activity(circle_id);
CREATE INDEX idx_circles_last_activity_at ON circles(last_activity_at);
CREATE INDEX idx_memberships_circle_id ON memberships(circle_id);