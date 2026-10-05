import sqlite3
import pandas as pd
from pathlib import Path
from helpers import tables, resolve_circle_topic, resolve_users_topic, resolve_circle_tags_topic

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR.parent / "lean_in_mock.db"

# Database connection and cursor initialization
db = sqlite3.connect(DB_PATH)
db.executescript((BASE_DIR / "schema.sql").read_text())
# SQLite does not enforce FKs
db.execute("PRAGMA foreign_keys = ON")

# Load topics lookup table for resolving topic slugs to IDs
topics_lookup = pd.read_json(DATA_DIR / "topics.json", orient='records')

# Load each table from the JSON files and resolve topic slugs to IDs where applicable
for name, path in tables.items():
    df = pd.read_json(DATA_DIR / path, orient='records')
    if name == "circles":
        df = resolve_circle_topic(df, topics_lookup)
        df.drop(columns=["tags"], inplace=True)
    if name == "users":
        df.drop(columns=["topic_interests"], inplace=True)
    df.to_sql(name, db, if_exists='append', index=False)

# Load the circle tags topic and resolve it using the topics lookup table
circle_tags_topic = pd.read_json(DATA_DIR / "circles.json", orient='records')
circle_tags_topic = resolve_circle_tags_topic(circle_tags_topic, topics_lookup)
circle_tags_topic.to_sql("circle_tags", db, if_exists='append', index=False)

# Load users topic and resolve it using the topics lookup table
users_topic = pd.read_json(DATA_DIR / "users.json", orient='records')
users_topic = resolve_users_topic(users_topic, topics_lookup)
users_topic.to_sql("user_topic_interests", db, if_exists='append', index=False)

# FK validation
assert db.execute("PRAGMA foreign_key_check").fetchall() == []

db.commit()

db.close()
