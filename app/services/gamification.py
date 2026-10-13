"""
Gamification, Taste Profiling, Milestone Badges, Leaderboards, and Polarization Intelligence
for Maanyankah (मान्यांकः).
"""

import json
from datetime import datetime, timedelta, timezone

def get_user_badges(db, user_id):
    """
    Compute real-time trusted reviewer tiers and milestone badges for a user.
    Returns:
        tier: dict(name, icon, css_class, description)
        milestones: list of dict(name, icon, description)
    """
    if not user_id:
        return {"tier": None, "milestones": []}

    rating_count = db.execute(
        "SELECT COUNT(*) FROM user_preferences WHERE user_id = ?", (user_id,)
    ).fetchone()[0]

    review_count = db.execute(
        "SELECT COUNT(*) FROM posts WHERE user_id = ? AND item_id IS NOT NULL", (user_id,)
    ).fetchone()[0]

    collection_count = db.execute(
        "SELECT COUNT(*) FROM collections WHERE user_id = ?", (user_id,)
    ).fetchone()[0]

    reaction_count = db.execute(
        """
        SELECT COUNT(*)
        FROM post_reactions pr
        JOIN posts p ON pr.post_id = p.id
        WHERE p.user_id = ?
        """,
        (user_id,),
    ).fetchone()[0]

    movie_ratings = db.execute(
        """
        SELECT COUNT(*)
        FROM user_preferences up
        JOIN items i ON up.item_id = i.id
        WHERE up.user_id = ? AND i.type = 'movie'
        """,
        (user_id,),
    ).fetchone()[0]

    song_ratings = db.execute(
        """
        SELECT COUNT(*)
        FROM user_preferences up
        JOIN items i ON up.item_id = i.id
        WHERE up.user_id = ? AND i.type = 'song'
        """,
        (user_id,),
    ).fetchone()[0]

    # 1. Reviewer Trust Tier
    if rating_count >= 10 and review_count >= 3:
        tier = {
            "name": "Top Critic",
            "icon": "👑",
            "badge_class": "badge-tier-top-critic",
            "description": "Verified Top Critic with deep catalog coverage and published reviews",
        }
    elif rating_count >= 4 or review_count >= 1:
        tier = {
            "name": "Trusted Reviewer",
            "icon": "⭐",
            "badge_class": "badge-tier-trusted",
            "description": "Trusted Community Reviewer with verified ratings activity",
        }
    else:
        tier = {
            "name": "Verified Fan",
            "icon": "🛡️",
            "badge_class": "badge-tier-verified",
            "description": "Authenticated Maanyankah Community Member",
        }

    # 2. Milestone Badges
    milestones = []
    if movie_ratings >= 3:
        milestones.append({
            "name": "Film Buff",
            "icon": "🎬",
            "description": f"Rated {movie_ratings}+ films across diverse genres",
        })
    if song_ratings >= 3:
        milestones.append({
            "name": "Audiophile",
            "icon": "🎵",
            "description": f"Explored and rated {song_ratings}+ audio tracks",
        })
    if collection_count >= 1:
        milestones.append({
            "name": "Master Curator",
            "icon": "📁",
            "description": f"Curated {collection_count} public watchlists and playlists",
        })
    if review_count >= 2:
        milestones.append({
            "name": "Prolific Voice",
            "icon": "✍️",
            "description": f"Shared {review_count} mindful reflections with the community",
        })
    if reaction_count >= 2:
        milestones.append({
            "name": "Community Resonant",
            "icon": "🔥",
            "description": f"Received {reaction_count}+ emotional reactions from fellow fans",
        })

    return {"tier": tier, "milestones": milestones}


def get_user_taste_profile(db, user_id):
    """
    Generate multidimensional taste breakdown: top genres, favorite creators,
    category distribution, and a cultural archetype title.
    """
    if not user_id:
        return None

    # Fetch all items user has rated
    rows = db.execute(
        """
        SELECT i.id, i.type, i.title, i.genre_tags, i.metadata, up.rating
        FROM user_preferences up
        JOIN items i ON up.item_id = i.id
        WHERE up.user_id = ?
        ORDER BY up.rating DESC, up.id DESC
        """,
        (user_id,),
    ).fetchall()

    if not rows:
        return {
            "has_data": False,
            "total_ratings": 0,
            "top_genres": [],
            "favorite_artists": [],
            "category_split": {"movie": 0, "song": 0, "team": 0},
            "archetype": "New Cultural Explorer",
        }

    genre_counts = {}
    artist_counts = {}
    cat_split = {"movie": 0, "song": 0, "team": 0}

    for r in rows:
        t = r["type"]
        if t in cat_split:
            cat_split[t] += 1

        # Genre tags
        raw_tags = r["genre_tags"] or ""
        for tag in raw_tags.split(","):
            tag_clean = tag.strip().title()
            if tag_clean:
                genre_counts[tag_clean] = genre_counts.get(tag_clean, 0) + 1

        # Metadata credits (director/artist)
        if r["metadata"]:
            try:
                meta = json.loads(r["metadata"])
                creator = meta.get("director") or meta.get("artist") or meta.get("league")
                if creator:
                    artist_counts[creator] = artist_counts.get(creator, 0) + 1
            except Exception:
                pass

    total_genres = sum(genre_counts.values()) or 1
    top_genres = sorted(
        [
            {"name": g, "count": c, "pct": round((c / total_genres) * 100)}
            for g, c in genre_counts.items()
        ],
        key=lambda x: x["count"],
        reverse=True,
    )[:5]

    favorite_artists = sorted(
        [{"name": a, "count": c} for a, c in artist_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:4]

    # Derive taste archetype title
    primary_genre = top_genres[0]["name"] if top_genres else "Cinema"
    if cat_split["movie"] >= cat_split["song"] and cat_split["movie"] > 0:
        archetype = f"{primary_genre} Cinephile & Story Enthusiast"
    elif cat_split["song"] > cat_split["movie"]:
        archetype = f"{primary_genre} Melophile & Audio Explorer"
    else:
        archetype = f"Eclectic {primary_genre} Connoisseur"

    return {
        "has_data": True,
        "total_ratings": len(rows),
        "top_genres": top_genres,
        "favorite_artists": favorite_artists,
        "category_split": cat_split,
        "archetype": archetype,
    }


def get_weekly_challenges(db, user_id=None):
    """
    Weekly cultural challenges with real user completion progress.
    """
    # 7-day window
    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

    recent_ratings = 0
    recent_reviews = 0
    recent_collections = 0

    if user_id:
        recent_ratings = db.execute(
            "SELECT COUNT(*) FROM user_preferences WHERE user_id = ? AND created_at >= ?",
            (user_id, seven_days_ago),
        ).fetchone()[0]

        recent_reviews = db.execute(
            "SELECT COUNT(*) FROM posts WHERE user_id = ? AND item_id IS NOT NULL AND created_at >= ?",
            (user_id, seven_days_ago),
        ).fetchone()[0]

        recent_collections = db.execute(
            "SELECT COUNT(*) FROM collections WHERE user_id = ? AND created_at >= ?",
            (user_id, seven_days_ago),
        ).fetchone()[0]

    challenges = [
        {
            "id": "rate_movies",
            "title": "🎬 Cinema Discovery Quest",
            "description": "Rate 3 movies in the catalog this week",
            "target": 3,
            "current": min(recent_ratings, 3),
            "completed": recent_ratings >= 3,
            "badge_reward": "Cinema Explorer",
        },
        {
            "id": "mindful_review",
            "title": "🌸 Mindful Review Challenge",
            "description": "Share 1 peaceful reflection with calming atmosphere vibe chips",
            "target": 1,
            "current": min(recent_reviews, 1),
            "completed": recent_reviews >= 1,
            "badge_reward": "Mindful Critic",
        },
        {
            "id": "curate_capsule",
            "title": "📁 Thematic Capsule Curator",
            "description": "Create 1 curated collection mixing films or songs",
            "target": 1,
            "current": min(recent_collections, 1),
            "completed": recent_collections >= 1,
            "badge_reward": "Capsule Master",
        },
    ]
    return challenges


def get_community_leaderboard(db, limit=10):
    """
    Compute community leaderboard for reviewers, curators, and engagement.
    """
    # 1. Top Reviewers
    reviewers = db.execute(
        """
        SELECT u.id, u.username, u.avatar_url, u.role,
               COUNT(DISTINCT up.id) AS ratings_count,
               COUNT(DISTINCT p.id) AS reviews_count,
               (COUNT(DISTINCT up.id) + COUNT(DISTINCT p.id) * 2) AS total_score
        FROM users u
        LEFT JOIN user_preferences up ON u.id = up.user_id
        LEFT JOIN posts p ON u.id = p.user_id AND p.item_id IS NOT NULL
        WHERE u.is_active = 1
        GROUP BY u.id
        HAVING total_score > 0
        ORDER BY total_score DESC, ratings_count DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    # 2. Top Curators
    curators = db.execute(
        """
        SELECT u.id, u.username, u.avatar_url, u.role,
               COUNT(DISTINCT c.id) AS collections_count,
               COUNT(DISTINCT cb.user_id) AS bookmarks_received,
               (COUNT(DISTINCT c.id) * 3 + COUNT(DISTINCT cb.user_id) * 2) AS curator_score
        FROM users u
        JOIN collections c ON u.id = c.user_id
        LEFT JOIN collection_bookmarks cb ON c.id = cb.collection_id
        WHERE u.is_active = 1
        GROUP BY u.id
        HAVING collections_count > 0
        ORDER BY curator_score DESC, collections_count DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    # 3. Community Pulse & Most Resonant Posts
    appreciated_users = db.execute(
        """
        SELECT u.id, u.username, u.avatar_url, u.role,
               COUNT(pr.id) AS reactions_received
        FROM users u
        JOIN posts p ON u.id = p.user_id
        JOIN post_reactions pr ON p.id = pr.post_id
        WHERE u.is_active = 1
        GROUP BY u.id
        HAVING reactions_received > 0
        ORDER BY reactions_received DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    return {
        "top_reviewers": [dict(r) for r in reviewers],
        "top_curators": [dict(c) for c in curators],
        "most_appreciated": [dict(a) for a in appreciated_users],
    }


def detect_polarization(stats):
    """
    Detect whether ratings for an item reveal audience polarization (e.g. cult classics
    with split love/hate) or consensus acclaim.
    Returns: dict(status, badge_class, label, description)
    """
    if not stats or not stats.get("rating_count"):
        return {
            "status": "unrated",
            "badge_class": "polarization-unrated",
            "label": "🌟 Unrated by Community",
            "description": "Be the first fan to review and set the benchmark!",
        }

    total = stats.get("rating_count", 0)
    if total < 2:
        return {
            "status": "early",
            "badge_class": "polarization-early",
            "label": "🌱 Early Impressions",
            "description": "Gathering initial community feedback.",
        }

    s1 = stats.get("stars_1", 0) or 0
    s2 = stats.get("stars_2", 0) or 0
    s4 = stats.get("stars_4", 0) or 0
    s5 = stats.get("stars_5", 0) or 0
    avg = stats.get("avg_rating", 0) or 0

    # Cult Classic / Bimodal Polarization: High 5-stars AND High 1-stars
    if total >= 3 and s1 > 0 and s5 > 0 and ((s1 + s5) / total) >= 0.5:
        return {
            "status": "cult_classic",
            "badge_class": "polarization-cult-classic",
            "label": "⚡ Cult Classic: Polarized Audience",
            "description": f"Passionate audience division ({s5} love vs {s1} hate). A true conversation-starter!",
        }

    # Universal Acclaim
    if ((s4 + s5) / total) >= 0.7 and avg >= 4.0:
        return {
            "status": "acclaim",
            "badge_class": "polarization-acclaim",
            "label": "🏆 Consensus Masterpiece",
            "description": f"Over {round(((s4+s5)/total)*100)}% of members rated this 4★ or 5★.",
        }

    # Solid & Well Liked
    if avg >= 3.5:
        return {
            "status": "positive",
            "badge_class": "polarization-positive",
            "label": "✨ Widely Enjoyed",
            "description": f"Reliably appreciated community average of {avg} / 5 ★.",
        }

    # Divided / Mixed
    return {
        "status": "mixed",
        "badge_class": "polarization-mixed",
        "label": "⚖️ Diverse Community Takes",
        "description": "Varied perspectives across individual viewer tastes.",
    }
