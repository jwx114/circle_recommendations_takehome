from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "lean_in_mock.db"

AS_OF_DATE = datetime(2026, 9, 21, tzinfo=timezone.utc)

# Default recommendation count
DEFAULT_K = 5

# Eligibility
RECOMMENDABLE_ACCESS = ("public",) # unlisted circles are not recommendable

# Scoring weights (0-1)
WEIGHTS = {
    "topic": 0.5,
    "activity": 0.3,
    "fit": 0.2
}

PRIMARY_TOPIC_MATCH = .0 # user.topic_interests == circle.topic
TAG_MATCH = 0.5 # user's topic interests appear in circle's tags BUT NOT its primary topic

# Inactivity: no penalty for first GRACE days, score halves every HALF_LIFE days
INACTIVITY_GRACE_DAYS = 14
INACTIVITY_HALF_LIFE_DAYS = 30

# Diversity, default maximum circles per topic, allowed up to 2
MAX_PER_TOPIC = 2

# Scoring
ACTIVITY_TARGETS = {
    "feed_posts_30d": 12,
    "chat_messages_30d": 150,
    "engagement_30d": 200
}
JOIN_POLICY_FIT = {"open": 1.0, "request": 0.6}
