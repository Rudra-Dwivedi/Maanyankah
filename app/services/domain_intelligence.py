"""
Domain Intelligence Service for मान्यांकः (Maanyankah)
Provides specialized multi-criteria evaluation engines for Movies, Songs, and Sports:
- Movies: Aspect ratings (Storyline, Acting, Direction, Cinematography, Music),
          Audience vs. Critic score split, Community mood tagging.
- Songs: Emotion-based impact, Replay value index, Lyrics vs. Music balance,
         Quick emoji reactions.
- Sports: Match Excitement Index, Player performance & MVP ratings,
          Outcome predictions & fan accuracy credibility, Highlight voting.
"""

from collections import Counter
import json


# ---------------------------------------------------------------------------
# 1. MOVIE INTELLIGENCE ENGINE
# ---------------------------------------------------------------------------

PRESET_MOVIE_MOODS = [
    {"tag": "chill", "label": "Chill & Relaxing", "icon": "🛋️"},
    {"tag": "intense", "label": "Edge-of-the-Seat Intense", "icon": "🔥"},
    {"tag": "family-friendly", "label": "Family-Friendly", "icon": "👨‍👩‍👧‍👦"},
    {"tag": "mind-bending", "label": "Mind-Bending & Clever", "icon": "🌌"},
    {"tag": "dark", "label": "Dark & Gritty", "icon": "🌑"},
    {"tag": "heartfelt", "label": "Heartfelt & Touching", "icon": "❤️"},
    {"tag": "tear-jerker", "label": "Tear-Jerker", "icon": "💧"},
    {"tag": "adrenalin", "label": "Adrenaline Rush", "icon": "⚡"},
]


def get_movie_aspect_ratings(db, item_id):
    """
    Calculate average ratings across 5 key cinematic criteria:
    Storyline, Acting, Direction, Cinematography, and Music.
    """
    row = db.execute(
        """
        SELECT 
            COUNT(*) as total_ratings,
            ROUND(AVG(storyline), 1) as avg_storyline,
            ROUND(AVG(acting), 1) as avg_acting,
            ROUND(AVG(direction), 1) as avg_direction,
            ROUND(AVG(cinematography), 1) as avg_cinematography,
            ROUND(AVG(music), 1) as avg_music
        FROM movie_aspect_ratings
        WHERE item_id = ?
        """,
        (item_id,),
    ).fetchone()

    total = row["total_ratings"] if row else 0
    if not row or total == 0:
        return {
            "has_aspects": False,
            "total_ratings": 0,
            "aspects": {
                "storyline": 0.0,
                "acting": 0.0,
                "direction": 0.0,
                "cinematography": 0.0,
                "music": 0.0,
            },
            "overall_aspect_avg": 0.0,
            "strongest_aspect": None,
        }

    aspects = {
        "storyline": float(row["avg_storyline"] or 0),
        "acting": float(row["avg_acting"] or 0),
        "direction": float(row["avg_direction"] or 0),
        "cinematography": float(row["avg_cinematography"] or 0),
        "music": float(row["avg_music"] or 0),
    }

    # Find highest rated craft element
    strongest = max(aspects.items(), key=lambda x: x[1])
    overall = round(sum(aspects.values()) / 5.0, 1)

    return {
        "has_aspects": True,
        "total_ratings": total,
        "aspects": aspects,
        "overall_aspect_avg": overall,
        "strongest_aspect": strongest[0] if strongest[1] > 0 else None,
    }


def get_movie_audience_vs_critic_split(db, item_id):
    """
    Computes separate Critic Score (Verified Critics/Admins) vs.
    Audience Score (General community members).
    """
    # 1. Critic Ratings
    critic_row = db.execute(
        """
        SELECT 
            COUNT(up.rating) as count,
            AVG(up.rating) as avg_rating
        FROM user_preferences up
        JOIN users u ON up.user_id = u.id
        WHERE up.item_id = ? AND (u.role = 'admin')
        """,
        (item_id,),
    ).fetchone()

    # 2. Audience Ratings (regular users)
    audience_row = db.execute(
        """
        SELECT 
            COUNT(up.rating) as count,
            AVG(up.rating) as avg_rating
        FROM user_preferences up
        JOIN users u ON up.user_id = u.id
        WHERE up.item_id = ? AND (u.role != 'admin' OR u.role IS NULL)
        """,
        (item_id,),
    ).fetchone()

    c_cnt = critic_row["count"] if critic_row else 0
    c_avg = round(float(critic_row["avg_rating"]), 1) if (critic_row and critic_row["avg_rating"]) else 0.0
    c_pct = int(round((c_avg / 5.0) * 100)) if c_avg > 0 else 0

    a_cnt = audience_row["count"] if audience_row else 0
    a_avg = round(float(audience_row["avg_rating"]), 1) if (audience_row and audience_row["avg_rating"]) else 0.0
    a_pct = int(round((a_avg / 5.0) * 100)) if a_avg > 0 else 0

    # Verdict on consensus or divergence
    if c_cnt > 0 and a_cnt > 0:
        diff = c_pct - a_pct
        if abs(diff) <= 8:
            verdict = "🤝 Universal Consensus: Both Critics & Audience Aligned"
            verdict_class = "consensus"
        elif diff > 8:
            verdict = f"👑 Critical Darling: Critics rate +{diff}% higher than Audience"
            verdict_class = "critic-favored"
        else:
            verdict = f"🍿 Fan Favorite: Audience rates +{abs(diff)}% higher than Critics"
            verdict_class = "audience-favored"
    elif a_cnt > 0:
        verdict = "👥 Fan Certified: Strong Community Audience Reception"
        verdict_class = "audience-only"
    else:
        verdict = "🌟 Awaiting First Verified Ratings"
        verdict_class = "unrated"

    return {
        "critic_count": c_cnt,
        "critic_avg": c_avg,
        "critic_pct": c_pct,
        "audience_count": a_cnt,
        "audience_avg": a_avg,
        "audience_pct": a_pct,
        "verdict": verdict,
        "verdict_class": verdict_class,
    }


def get_item_mood_tags(db, item_id, limit=6):
    """Returns top community mood tags for a movie or song with counts."""
    rows = db.execute(
        """
        SELECT mood, COUNT(*) as tag_count
        FROM item_mood_tags
        WHERE item_id = ?
        GROUP BY mood
        ORDER BY tag_count DESC, mood ASC
        LIMIT ?
        """,
        (item_id, limit),
    ).fetchall()

    return [{"mood": r["mood"], "count": r["tag_count"]} for r in rows]


# ---------------------------------------------------------------------------
# 2. SONG INTELLIGENCE ENGINE
# ---------------------------------------------------------------------------

PRESET_SONG_EMOTIONS = [
    {"tag": "energetic", "label": "⚡ High Energy", "color": "#f59e0b"},
    {"tag": "chill", "label": "🌿 Chill & Mellow", "color": "#10b981"},
    {"tag": "happy", "label": "☀️ Euphoric & Happy", "color": "#ec4899"},
    {"tag": "sad", "label": "💧 Melancholic & Sad", "color": "#3b82f6"},
    {"tag": "romantic", "label": "❤️ Soulful & Romantic", "color": "#ef4444"},
]

QUICK_REACTION_META = {
    "fire": {"icon": "🔥", "label": "Banger / Fire"},
    "love": {"icon": "❤️", "label": "Love It"},
    "vibe": {"icon": "🎶", "label": "Immaculate Vibe"},
    "energetic": {"icon": "⚡", "label": "Pure Energy"},
    "masterpiece": {"icon": "🎧", "label": "Audiophile Masterpiece"},
}


def get_song_evaluation_summary(db, item_id):
    """
    Returns aggregated song metrics:
    - Dominant emotional impact
    - Replay value score and verbal frequency label
    - Lyrics vs Music split ratings and craft balance ratio
    """
    rows = db.execute(
        """
        SELECT 
            COUNT(*) as total_evals,
            AVG(replay_value) as avg_replay,
            AVG(lyrics_score) as avg_lyrics,
            AVG(music_score) as avg_music
        FROM song_evaluations
        WHERE item_id = ?
        """,
        (item_id,),
    ).fetchone()

    total = rows["total_evals"] if rows else 0
    if not rows or total == 0:
        return {
            "has_evals": False,
            "total_evals": 0,
            "dominant_emotion": None,
            "replay_value": 0.0,
            "replay_label": "Not enough data",
            "lyrics_score": 0.0,
            "music_score": 0.0,
            "balance_verdict": "Unrated",
        }

    avg_replay = round(float(rows["avg_replay"] or 0), 1)
    avg_lyrics = round(float(rows["avg_lyrics"] or 0), 1)
    avg_music = round(float(rows["avg_music"] or 0), 1)

    # Calculate Replay Value verbal label
    if avg_replay >= 4.3:
        replay_label = "🔥 Daily on Repeat"
    elif avg_replay >= 3.5:
        replay_label = "🎧 Heavy Rotation"
    elif avg_replay >= 2.5:
        replay_label = "📻 Occasional Vibe"
    else:
        replay_label = "⏳ Selective Listen"

    # Dominant Emotion calculation
    emotion_rows = db.execute(
        """
        SELECT emotion, COUNT(*) as cnt
        FROM song_evaluations
        WHERE item_id = ? AND emotion IS NOT NULL AND emotion != ''
        GROUP BY emotion
        ORDER BY cnt DESC
        LIMIT 1
        """,
        (item_id,),
    ).fetchone()
    dominant_emotion = emotion_rows["emotion"] if emotion_rows else None

    # Lyrics vs Music Balance Verdict
    if avg_lyrics > 0 and avg_music > 0:
        diff = avg_lyrics - avg_music
        if abs(diff) <= 0.4:
            balance_verdict = "⚖️ Harmonious Balance: Equal lyrical & musical mastery"
        elif diff > 0.4:
            balance_verdict = f"📖 Lyrical Powerhouse: Lyrical depth outshines production by +{round(diff, 1)}"
        else:
            balance_verdict = f"🎹 Sonic Euphoria: Production & arrangement lead by +{round(abs(diff), 1)}"
    else:
        balance_verdict = "Balanced Composition"

    return {
        "has_evals": True,
        "total_evals": total,
        "dominant_emotion": dominant_emotion,
        "replay_value": avg_replay,
        "replay_label": replay_label,
        "lyrics_score": avg_lyrics,
        "music_score": avg_music,
        "balance_verdict": balance_verdict,
    }


def get_item_quick_reactions(db, item_id, user_id=None):
    """
    Returns quick emoji reactions aggregate counts for an item or song,
    and indicates whether the current user has reacted.
    """
    rows = db.execute(
        """
        SELECT reaction, COUNT(*) as count
        FROM item_quick_reactions
        WHERE item_id = ?
        GROUP BY reaction
        """,
        (item_id,),
    ).fetchall()

    counts = {k: 0 for k in QUICK_REACTION_META.keys()}
    for r in rows:
        if r["reaction"] in counts:
            counts[r["reaction"]] = r["count"]

    user_reaction = None
    if user_id:
        u_row = db.execute(
            "SELECT reaction FROM item_quick_reactions WHERE item_id = ? AND user_id = ?",
            (item_id, user_id),
        ).fetchone()
        if u_row:
            user_reaction = u_row["reaction"]

    return {
        "counts": counts,
        "total": sum(counts.values()),
        "user_reaction": user_reaction,
    }


# ---------------------------------------------------------------------------
# 3. SPORTS INTELLIGENCE ENGINE
# ---------------------------------------------------------------------------

HIGHLIGHT_TYPE_META = {
    "best_play": {"icon": "⚡", "label": "Best Play / Skill"},
    "turning_point": {"icon": "🔄", "label": "Turning Point of Match"},
    "clutch_moment": {"icon": "🛡️", "label": "Clutch Save / Defensive Stop"},
    "mvp_performance": {"icon": "👑", "label": "Player of the Match Moment"},
}


def get_sports_match_summary(db, item_id):
    """
    Calculates the Match Excitement Index:
    - Thrill level (1-5)
    - Competitiveness (1-5)
    - Memorable moments (1-5)
    Composite Index: 0 to 100 score with excitement badge tier.
    """
    row = db.execute(
        """
        SELECT 
            COUNT(*) as total_ratings,
            AVG(thrill_level) as avg_thrill,
            AVG(competitiveness) as avg_comp,
            AVG(memorable_moments) as avg_mem
        FROM sports_match_ratings
        WHERE item_id = ?
        """,
        (item_id,),
    ).fetchone()

    total = row["total_ratings"] if row else 0
    if not row or total == 0:
        return {
            "has_ratings": False,
            "total_ratings": 0,
            "thrill_level": 0.0,
            "competitiveness": 0.0,
            "memorable_moments": 0.0,
            "excitement_index": 0,
            "excitement_tier": "Unrated Match",
            "excitement_badge_class": "badge-unrated",
        }

    thrill = round(float(row["avg_thrill"] or 0), 1)
    comp = round(float(row["avg_comp"] or 0), 1)
    mem = round(float(row["avg_mem"] or 0), 1)

    # Index out of 100
    excitement_index = int(round(((thrill + comp + mem) / 15.0) * 100))

    if excitement_index >= 88:
        tier = "⚡ Instant Classic / Legendary Thriller"
        badge_class = "badge-classic"
    elif excitement_index >= 75:
        tier = "🔥 High Drama & Edge-of-Seat Action"
        badge_class = "badge-high-drama"
    elif excitement_index >= 60:
        tier = "⚔️ Highly Competitive Contest"
        badge_class = "badge-competitive"
    else:
        tier = "📋 Standard Routine Fixture"
        badge_class = "badge-standard"

    return {
        "has_ratings": True,
        "total_ratings": total,
        "thrill_level": thrill,
        "competitiveness": comp,
        "memorable_moments": mem,
        "excitement_index": excitement_index,
        "excitement_tier": tier,
        "excitement_badge_class": badge_class,
    }


def get_sports_highlight_votes(db, item_id):
    """
    Retrieves fan votes on highlights: Best Play, Turning Point, Clutch Moment.
    """
    rows = db.execute(
        """
        SELECT highlight_type, highlight_title, COUNT(*) as vote_count
        FROM sports_highlight_votes
        WHERE item_id = ?
        GROUP BY highlight_type, highlight_title
        ORDER BY vote_count DESC
        LIMIT 8
        """,
        (item_id,),
    ).fetchall()

    return [
        {
            "type": r["highlight_type"],
            "title": r["highlight_title"],
            "votes": r["vote_count"],
            "meta": HIGHLIGHT_TYPE_META.get(r["highlight_type"], {"icon": "🏆", "label": "Highlight"}),
        }
        for r in rows
    ]


def get_sports_predictions_summary(db, item_id, user_id=None):
    """
    Returns fan prediction breakdown for upcoming/recent matches.
    """
    rows = db.execute(
        """
        SELECT predicted_outcome, COUNT(*) as count
        FROM sports_predictions
        WHERE item_id = ?
        GROUP BY predicted_outcome
        ORDER BY count DESC
        """,
        (item_id,),
    ).fetchall()

    total_preds = sum(r["count"] for r in rows)
    breakdown = []
    for r in rows:
        pct = int(round((r["count"] / total_preds * 100))) if total_preds > 0 else 0
        breakdown.append({
            "outcome": r["predicted_outcome"],
            "count": r["count"],
            "percentage": pct,
        })

    user_pred = None
    if user_id:
        u_pred = db.execute(
            "SELECT * FROM sports_predictions WHERE item_id = ? AND user_id = ?",
            (item_id, user_id),
        ).fetchone()
        if u_pred:
            user_pred = dict(u_pred)

    return {
        "total_predictions": total_preds,
        "breakdown": breakdown,
        "user_prediction": user_pred,
    }


def get_sports_prediction_leaderboard(db, limit=10):
    """
    Ranks sports community members by prediction accuracy & credibility points.
    """
    rows = db.execute(
        """
        SELECT 
            u.id as user_id,
            u.username,
            u.avatar_url,
            COUNT(sp.id) as total_predictions,
            SUM(CASE WHEN sp.is_correct = 1 THEN 1 ELSE 0 END) as correct_predictions,
            SUM(COALESCE(sp.points_awarded, 0)) as total_points
        FROM sports_predictions sp
        JOIN users u ON sp.user_id = u.id
        GROUP BY u.id
        HAVING total_predictions > 0
        ORDER BY total_points DESC, correct_predictions DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    leaderboard = []
    for rank, r in enumerate(rows, 1):
        total = r["total_predictions"]
        correct = r["correct_predictions"]
        acc = int(round((correct / total * 100))) if total > 0 else 0
        leaderboard.append({
            "rank": rank,
            "user_id": r["user_id"],
            "username": r["username"],
            "avatar_url": r["avatar_url"],
            "total_predictions": total,
            "correct_predictions": correct,
            "accuracy_pct": acc,
            "total_points": r["total_points"],
        })
    return leaderboard
