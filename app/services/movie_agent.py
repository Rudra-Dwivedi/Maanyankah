"""
Movie & Ratings Intelligence Agent for Maanyankah.
Analyzes catalog movies, calculates deep platform community ratings breakdown,
inspects member review sentiment, and provides film insights and recommendations.
"""

import json
import re
import os
from flask import g
from app.db import get_db
from app.services.item_media import resolve_image_url
from app.services.settings_store import get_setting

# Known fallback details for catalog starter movies to ensure rich trivia and synopsis
MOVIE_KNOWLEDGE_BASE = {
    "inception": {
        "director": "Christopher Nolan",
        "year": "2010",
        "genres": ["Sci-Fi", "Action", "Thriller"],
        "synopsis": "A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea into the mind of a C.E.O.",
        "themes": "Subconscious reality, grief, perception of time, memory architecting",
        "runtime": "148 mins",
        "verdict": "Widely praised for mind-bending narrative pacing, iconic Hans Zimmer score, and breathtaking practical visual effects.",
    },
    "the dark knight": {
        "director": "Christopher Nolan",
        "year": "2008",
        "genres": ["Action", "Crime", "Drama"],
        "synopsis": "When the menace known as the Joker wreaks havoc and chaos on the people of Gotham, Batman must accept one of the greatest psychological and physical tests of his ability to fight injustice.",
        "themes": "Morality, escalation, chaos vs order, heroism and sacrifice",
        "runtime": "152 mins",
        "verdict": "Considered a landmark masterwork of modern cinema, distinguished by Heath Ledger's legendary Oscar-winning performance as the Joker.",
    },
    "la la land": {
        "director": "Damien Chazelle",
        "year": "2016",
        "genres": ["Romance", "Musical", "Drama"],
        "synopsis": "While navigating their careers in Los Angeles, a pianist and an aspiring actress fall in love while attempting to reconcile their aspirations for the future.",
        "themes": "Artistic passion vs compromise, bittersweet nostalgia, destiny and love",
        "runtime": "128 mins",
        "verdict": "An intoxicating, vibrant tribute to classic Hollywood musicals with magnificent chemistry between Ryan Gosling and Emma Stone.",
    },
    "parasite": {
        "director": "Bong Joon-ho",
        "year": "2019",
        "genres": ["Thriller", "Black Comedy", "Drama"],
        "synopsis": "Greed and class discrimination threaten the newly formed symbiotic relationship between the wealthy Park family and the destitute Kim clan.",
        "themes": "Socioeconomic disparity, parasitic symbiosis, pride, invisible class barriers",
        "runtime": "132 mins",
        "verdict": "Historic 4-time Oscar winner (including Best Picture); a masterclass in tension, social commentary, and immaculate genre shifting.",
    },
    "the grand budapest hotel": {
        "director": "Wes Anderson",
        "year": "2014",
        "genres": ["Comedy", "Adventure", "Crime"],
        "synopsis": "A writer encounters the owner of an aging high-class hotel, who tells him of his early years serving as a lobby boy in the hotel's glorious years under an exceptional concierge.",
        "themes": "Fading elegance, loyalty, friendship, wartime European nostalgia",
        "runtime": "99 mins",
        "verdict": "A visual feast packed with Anderson's trademark symmetrical pastels, witty dialogue, and an unforgettable performance by Ralph Fiennes.",
    },
}


def get_movie_stats(db, item_id):
    """Compute detailed rating statistics and reviews for a specific movie."""
    # Rating stats
    ratings = db.execute(
        """
        SELECT p.rating, u.username, u.avatar_url
        FROM user_preferences p
        JOIN users u ON p.user_id = u.id
        WHERE p.item_id = ?
        ORDER BY p.created_at DESC
        """,
        (item_id,),
    ).fetchall()

    total_ratings = len(ratings)
    avg_rating = round(sum(r["rating"] for r in ratings) / total_ratings, 1) if total_ratings > 0 else 0.0

    breakdown = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for r in ratings:
        breakdown[r["rating"]] = breakdown.get(r["rating"], 0) + 1

    pct_breakdown = {}
    for star in range(5, 0, -1):
        pct = round((breakdown[star] / total_ratings * 100), 1) if total_ratings > 0 else 0
        pct_breakdown[star] = {"count": breakdown[star], "pct": pct}

    # Tagged posts from community feed
    posts = db.execute(
        """
        SELECT posts.content, posts.sentiment_score, posts.created_at, users.username, users.avatar_url
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE posts.item_id = ?
        ORDER BY posts.created_at DESC
        LIMIT 6
        """,
        (item_id,),
    ).fetchall()

    positive_posts = sum(1 for p in posts if p["sentiment_score"] > 0.15)
    negative_posts = sum(1 for p in posts if p["sentiment_score"] < -0.15)
    neutral_posts = len(posts) - (positive_posts + negative_posts)

    if total_ratings == 0 and len(posts) == 0:
        sentiment_summary = "No ratings or community reviews logged yet on Maanyankah."
    elif avg_rating >= 4.2:
        sentiment_summary = "🔥 Overwhelmingly Loved by the community — a verified crowd favorite!"
    elif avg_rating >= 3.5:
        sentiment_summary = "✨ Positively Received with strong appreciation among members."
    elif avg_rating >= 2.5:
        sentiment_summary = "⚖️ Mixed Impressions — opinions are divided across the audience."
    else:
        sentiment_summary = "Critical reception — members have voiced reservations."

    return {
        "avg_rating": avg_rating,
        "rating_count": total_ratings,
        "breakdown": pct_breakdown,
        "recent_raters": [{"username": r["username"], "rating": r["rating"]} for r in ratings[:4]],
        "posts": [dict(p) for p in posts],
        "sentiment_summary": sentiment_summary,
        "sentiment_counts": {
            "positive": positive_posts,
            "neutral": neutral_posts,
            "negative": negative_posts,
        },
    }


def find_movies_by_keyword(db, query):
    """Find catalog movies matching a query string by title."""
    q_norm = query.strip().lower()
    # Strip common conversational question prefixes
    for prefix in ["tell me about", "what is the rating of", "what is the rating for", "what is", "what are", "ratings for", "rating of", "how good is", "details on", "tell about"]:
        if q_norm.startswith(prefix):
            q_norm = q_norm[len(prefix):].strip()

    movies = db.execute(
        "SELECT * FROM items WHERE type = 'movie' ORDER BY title"
    ).fetchall()

    matched = []
    for m in movies:
        title_lower = m["title"].lower()
        # Direct or substring match on movie title
        if title_lower == q_norm or title_lower in q_norm:
            matched.append(m)
        elif len(q_norm) >= 4 and q_norm in title_lower:
            matched.append(m)
    return matched


def get_top_rated_movies(db, limit=5):
    """Return top movies ranked by community average rating."""
    rows = db.execute(
        """
        SELECT i.*, 
               COALESCE(ROUND(AVG(p.rating), 1), 0) AS avg_rating,
               COUNT(p.rating) AS rating_count
        FROM items i
        LEFT JOIN user_preferences p ON i.id = p.item_id
        WHERE i.type = 'movie'
        GROUP BY i.id
        ORDER BY avg_rating DESC, rating_count DESC, i.title ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return rows


def ask_movie_agent(query):
    """
    Main processing function for the Movie Agent.
    Handles natural language queries, movie specific inquiries,
    ranking requests, and recommendations.
    """
    db = get_db()
    clean_q = query.strip()
    lower_q = clean_q.lower()

    # 1. Check for Ranking / Top Movies request
    ranking_triggers = [
        "top rated", "highest rated", "best movies", "top movie", "leaderboard",
        "rankings", "highest rating", "best rated", "most popular", "highest"
    ]
    if any(trigger in lower_q for trigger in ranking_triggers) and not any(k in lower_q for k in MOVIE_KNOWLEDGE_BASE):
        top_movies = get_top_rated_movies(db, limit=6)
        items_payload = []
        for m in top_movies:
            img = resolve_image_url(m)
            items_payload.append({
                "id": m["id"],
                "title": m["title"],
                "genres": m["genre_tags"],
                "avg_rating": m["avg_rating"],
                "rating_count": m["rating_count"],
                "image_url": img,
            })

        return {
            "type": "ranking",
            "title": "🏆 Highest Rated Movies on Maanyankah",
            "message": (
                "Here are the top-rated films on Maanyankah based on community scores! "
                "These have earned the highest appreciation among our members:"
            ),
            "movies": items_payload,
            "suggestions": [
                "Tell me about Inception",
                "What are the ratings for Parasite?",
                "Suggest a thrilling movie"
            ]
        }

    # 2. Check for Recommendation / Suggestion requests
    is_rec_query = any(k in lower_q for k in ["recommend", "suggest", "what should i watch", "good movie", "pick a movie", "give me a movie"])
    genre_keywords = {
        "sci-fi": "Sci-Fi",
        "thriller": "Thriller",
        "drama": "Drama",
        "action": "Action",
        "comedy": "Comedy",
        "romance": "Romance",
        "musical": "Musical",
    }
    found_genre = None
    for k, v in genre_keywords.items():
        if k in lower_q:
            found_genre = v
            break

    if is_rec_query or (found_genre and not any(m["title"].lower() in lower_q for m in db.execute("SELECT title FROM items WHERE type = 'movie'").fetchall())):
        if found_genre:
            query_sql = "SELECT * FROM items WHERE type = 'movie' AND (genre_tags LIKE ? OR title LIKE ?) ORDER BY title"
            rows = db.execute(query_sql, (f"%{found_genre}%", f"%{found_genre}%")).fetchall()
        else:
            rows = db.execute("SELECT * FROM items WHERE type = 'movie' ORDER BY RANDOM() LIMIT 4").fetchall()

        rec_payload = []
        for m in rows:
            img = resolve_image_url(m)
            stats = get_movie_stats(db, m["id"])
            rec_payload.append({
                "id": m["id"],
                "title": m["title"],
                "genres": m["genre_tags"],
                "avg_rating": stats["avg_rating"],
                "rating_count": stats["rating_count"],
                "image_url": img,
            })

        return {
            "type": "recommendations",
            "title": f"🎬 Movie Recommendations{f' ({found_genre})' if found_genre else ''}",
            "message": f"Looking for great cinema? Here are {len(rec_payload)} hand-picked recommendations from the Maanyankah catalog with real ratings:",
            "movies": rec_payload,
            "suggestions": [
                "Tell me about Inception",
                "What is the average rating of The Dark Knight?",
                "What are the top rated movies?"
            ]
        }

    # 3. Check for Specific Movie Lookup
    matched_movies = find_movies_by_keyword(db, lower_q)
    if matched_movies:
        primary_movie = matched_movies[0]
        stats = get_movie_stats(db, primary_movie["id"])
        image_url = resolve_image_url(primary_movie)

        # Retrieve knowledge base details if available
        norm_title = primary_movie["title"].lower().strip()
        kb = MOVIE_KNOWLEDGE_BASE.get(norm_title, {})
        
        # Meta parse
        metadata = {}
        if primary_movie["metadata"]:
            try:
                metadata = json.loads(primary_movie["metadata"])
            except Exception:
                pass

        director = kb.get("director", metadata.get("director", "Acclaimed Filmmaker"))
        year = kb.get("year", metadata.get("release_date", "")[:4] or "Classic")
        genres = kb.get("genres", [g.strip() for g in (primary_movie["genre_tags"] or "").split(",") if g.strip()] or ["Drama"])
        synopsis = kb.get("synopsis", metadata.get("overview") or f"{primary_movie['title']} is a featured favorite on Maanyankah.")
        verdict = kb.get("verdict", "Highly discussed across cinema communities and loved for its bold storytelling.")

        return {
            "type": "movie_detail",
            "movie": {
                "id": primary_movie["id"],
                "title": primary_movie["title"],
                "director": director,
                "year": year,
                "genres": genres,
                "synopsis": synopsis,
                "verdict": verdict,
                "image_url": image_url,
                "stats": stats,
            },
            "message": f"Here is everything about **{primary_movie['title']}**, including its community ratings on Maanyankah:",
            "suggestions": [
                f"What are the highest rated movies on Maanyankah?",
                f"Who gave {primary_movie['title']} 5 stars?",
                f"Recommend something like {primary_movie['title']}"
            ]
        }

    # 3. Genre / Recommendation Request
    genre_keywords = {
        "sci-fi": "Sci-Fi",
        "thriller": "Thriller",
        "drama": "Drama",
        "action": "Action",
        "comedy": "Comedy",
        "romance": "Romance",
        "musical": "Musical",
    }
    found_genre = None
    for k, v in genre_keywords.items():
        if k in lower_q:
            found_genre = v
            break

    if found_genre or "recommend" in lower_q or "suggest" in lower_q or "good movie" in lower_q:
        db = get_db()
        if found_genre:
            query_sql = "SELECT * FROM items WHERE type = 'movie' AND genre_tags LIKE ? ORDER BY title"
            rows = db.execute(query_sql, (f"%{found_genre}%",)).fetchall()
        else:
            rows = db.execute("SELECT * FROM items WHERE type = 'movie' ORDER BY RANDOM() LIMIT 4").fetchall()

        rec_payload = []
        for m in rows:
            img = resolve_image_url(m)
            stats = get_movie_stats(db, m["id"])
            rec_payload.append({
                "id": m["id"],
                "title": m["title"],
                "genres": m["genre_tags"],
                "avg_rating": stats["avg_rating"],
                "rating_count": stats["rating_count"],
                "image_url": img,
            })

        return {
            "type": "recommendations",
            "title": f"🎬 Movie Recommendations{f' ({found_genre})' if found_genre else ''}",
            "message": f"Looking for great cinema? Here are {len(rec_payload)} hand-picked recommendations from the Maanyankah catalog with real ratings:",
            "movies": rec_payload,
            "suggestions": [
                "Tell me about Inception",
                "What is the average rating of The Dark Knight?",
                "What are the top rated movies?"
            ]
        }

    # 4. Fallback / Helpful conversational guidance
    return {
        "type": "general",
        "title": "चित्राङ्कः (Chitrankah) at your service",
        "message": (
            f"नमस्ते! I am **चित्राङ्कः (Chitrankah)**, your cinema & ratings intelligence agent. "
            f"I can tell you everything about movies in our catalog—including director notes, "
            f"synopsis, themes, and **real community ratings & reviews** logged by Maanyankah members!\n\n"
            f"Try asking about a specific film, community rating trends, or ask for a movie recommendation."
        ),
        "suggestions": [
            "Tell me about Inception",
            "What is the rating of The Dark Knight?",
            "What is the highest rated movie?",
            "Tell me about Parasite",
            "Recommend a sci-fi thriller"
        ]
    }
