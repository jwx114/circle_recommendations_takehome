tables = {
    "users": ("users.json"),
    "topics": ("topics.json"),
    "circles": ("circles.json"),
    "memberships": ("memberships.json"),
    "activity": ("activity.json"),
}

def resolve_circle_topic(df, topics_lookup):
    # Trim topics_lookup to only include the necessary columns before renaming
    topics_lookup = topics_lookup[["id", "slug"]].rename(columns={"id": "topic_id", "slug": "topic_slug"})
    # Merge the circle dataframe with the topics lookup to get topic details and drop redundant topic & topic_slug columns
    df = (df.merge(topics_lookup, left_on="topic", right_on="topic_slug", how="left")
           .drop(columns=["topic", "topic_slug"])
          )
    return df

def resolve_circle_tags_topic(df, topics_lookup):
    topics_lookup = topics_lookup[["id", "slug"]].rename(columns={"id": "topic_id", "slug": "topic_slug"})
    df = (
        df[["id", "tags"]]
            .rename(columns={"id": "circle_id"})
            .explode("tags")
            .merge(topics_lookup, left_on="tags", right_on="topic_slug", how="left")
            .dropna() # Drops rows with missing tags
            .drop(columns=["tags", "topic_slug"])
            .drop_duplicates()
           )
    return df

def resolve_users_topic(df, topics_lookup):
    topics_lookup = topics_lookup[["id", "slug"]].rename(columns={"id": "topic_id", "slug": "topic_slug"})
    df = (
        df[["id", "topic_interests"]]
            .rename(columns={"id": "user_id"})
            .explode("topic_interests")
            .merge(topics_lookup, left_on="topic_interests", right_on="topic_slug", how="left")
            .dropna() # same as above but with topic_interests
            .drop(columns=["topic_interests", "topic_slug"])
            .drop_duplicates()
           )
    return df