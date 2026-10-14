import json
from flask import Blueprint, render_template, request, redirect, url_for, g, flash, jsonify, abort

from app.db import get_db
from app.auth_utils import login_required
from app.services.item_media import with_image_urls, resolve_image_url
from app.services.sentiment import analyze, label
from app.services.movie_agent import MOVIE_KNOWLEDGE_BASE, SONG_KNOWLEDGE_BASE, resolve_movie_trailer
from app.services.gamification import detect_polarization, get_user_badges, get_weekly_challenges
from app.services.recommender import predict_rating
from app.services.domain_intelligence import (
    PRESET_MOVIE_MOODS,
    PRESET_SONG_EMOTIONS,
    QUICK_REACTION_META,
    HIGHLIGHT_TYPE_META,
    get_movie_aspect_ratings,
    get_movie_audience_vs_critic_split,
    get_item_mood_tags,
    get_song_evaluation_summary,
    get_item_quick_reactions,
    get_sports_match_summary,
    get_sports_highlight_votes,
    get_sports_predictions_summary,
    get_sports_prediction_leaderboard,
)

bp = Blueprint("items", __name__, url_prefix="/items")


def get_item_metadata_and_description(item):
    """Extract and enrich metadata, narrative overview, and credits for an item."""
    meta = {}
    raw_meta = item.get("metadata") if isinstance(item, dict) else item["metadata"]
    if raw_meta:
        try:
            meta = json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta
        except Exception:
            meta = {}

    title = item["title"]
    item_type = item["type"]
    clean_title = title.strip().lower()

    description = meta.get("overview") or meta.get("description") or ""
    release_date = meta.get("release_date") or ""
    vote_average = meta.get("vote_average") or 0
    director = meta.get("director") or ""
    cast = meta.get("cast") or ""
    artist = meta.get("artist") or ""
    album = meta.get("album") or ""
    runtime = meta.get("runtime") or ""
    vibe = meta.get("vibe") or ""
    themes = meta.get("themes") or ""

    # Knowledge base enrichment if needed
    if item_type == "movie":
        kb = MOVIE_KNOWLEDGE_BASE.get(clean_title)
        if kb:
            if not description or len(description) < 40:
                description = kb.get("synopsis") or description
            director = director or kb.get("director", "")
            cast = cast or kb.get("cast", "")
            runtime = runtime or kb.get("runtime", "")
            themes = themes or kb.get("themes", "")
        if not description:
            description = f"An acclaimed film in the {item.get('genre_tags') or 'popular cinema'} genre, celebrated by the community for its compelling narrative and creative direction."

    elif item_type == "song":
        kb = SONG_KNOWLEDGE_BASE.get(clean_title)
        if kb:
            if not description or len(description) < 40:
                description = kb.get("meaning") or kb.get("narrative") or kb.get("vibe") or description
            artist = artist or kb.get("artist", "")
            album = album or kb.get("album", "")
            runtime = runtime or kb.get("duration", "")
            vibe = vibe or kb.get("vibe", "")
        if not description:
            description = f"An iconic musical recording in {item.get('genre_tags') or 'popular music'}, recognized for its distinctive production, rhythmic energy, and listener appeal."

    elif item_type == "team":
        if not description:
            league_str = f" competing in {item.get('genre_tags')}" if item.get("genre_tags") else ""
            description = f"A prestigious sports franchise and fan collective{league_str}, renowned for championship legacy, passionate stadium crowds, and competitive excellence."

    tags_raw = item.get("genre_tags") or ""
    genres = [t.strip() for t in tags_raw.split(",") if t.strip()]

    return {
        "description": description,
        "release_date": release_date,
        "vote_average": vote_average,
        "director": director,
        "cast": cast,
        "artist": artist,
        "album": album,
        "runtime": runtime,
        "vibe": vibe,
        "themes": themes,
        "genres": genres,
        "extra_meta": meta,
    }


@bp.route("/")
def browse():
    """Browse items, with keyword search and multi-faceted filtering (type, genre, rating, era, sorting)."""
    item_type = request.args.get("type", "").strip().lower()
    if item_type not in ("movie", "song", "team"):
        item_type = None

    search_query = request.args.get("q", "").strip()
    active_genre = request.args.get("genre", "").strip().lower()
    min_rating = request.args.get("min_rating", "").strip().lower()
    active_sort = request.args.get("sort", "newest").strip().lower()
    active_era = request.args.get("era", "").strip().lower()
    active_mood = request.args.get("mood", "").strip().lower()

    db = get_db()

    # Query distinct genre tags for the active type filter
    tag_sql = "SELECT genre_tags FROM items WHERE genre_tags IS NOT NULL AND genre_tags != ''"
    tag_params = []
    if item_type:
        tag_sql += " AND type = ?"
        tag_params.append(item_type)
    tag_rows = db.execute(tag_sql, tag_params).fetchall()

    genre_counts = {}
    for r in tag_rows:
        raw = r["genre_tags"] or ""
        tags = [t.strip().lower() for t in raw.split(",") if t.strip()]
        for t in tags:
            genre_counts[t] = genre_counts.get(t, 0) + 1

    available_genres = [
        {"tag": t, "label": t.title(), "count": genre_counts[t]}
        for t in sorted(genre_counts.keys())
    ]

    # Build SQL query with optional type, genre, search, era, and mood filtering
    where_clauses = []
    params = []

    if item_type:
        where_clauses.append("i.type = ?")
        params.append(item_type)

    if active_genre:
        where_clauses.append("(',' || LOWER(REPLACE(i.genre_tags, ' ', '')) || ',') LIKE ?")
        params.append(f"%,{active_genre.replace(' ', '')},%")

    if search_query:
        q_clean = search_query.lower()
        where_clauses.append("(LOWER(i.title) LIKE ? OR LOWER(i.genre_tags) LIKE ? OR LOWER(i.metadata) LIKE ?)")
        params.extend([f"%{q_clean}%", f"%{q_clean}%", f"%{q_clean}%"])

    if active_era:
        if active_era == "2020s":
            where_clauses.append("(i.metadata LIKE '%\"release_date\": \"202%' OR i.metadata LIKE '%\"release_date\":\"202%')")
        elif active_era == "2010s":
            where_clauses.append("(i.metadata LIKE '%\"release_date\": \"201%' OR i.metadata LIKE '%\"release_date\":\"201%')")
        elif active_era == "2000s":
            where_clauses.append("(i.metadata LIKE '%\"release_date\": \"200%' OR i.metadata LIKE '%\"release_date\":\"200%')")
        elif active_era in ("classic", "older"):
            where_clauses.append("(i.metadata LIKE '%\"release_date\": \"19%' OR i.metadata LIKE '%\"release_date\":\"19%')")

    if active_mood:
        if active_mood == "mind-bending":
            where_clauses.append("(LOWER(i.genre_tags) LIKE '%sci-fi%' OR LOWER(i.genre_tags) LIKE '%thriller%' OR LOWER(i.genre_tags) LIKE '%mystery%')")
        elif active_mood == "feel-good":
            where_clauses.append("(LOWER(i.genre_tags) LIKE '%musical%' OR LOWER(i.genre_tags) LIKE '%comedy%' OR LOWER(i.genre_tags) LIKE '%pop%' OR LOWER(i.genre_tags) LIKE '%dance%' OR LOWER(i.genre_tags) LIKE '%disco%')")
        elif active_mood == "adrenaline":
            where_clauses.append("(LOWER(i.genre_tags) LIKE '%action%' OR LOWER(i.genre_tags) LIKE '%crime%' OR LOWER(i.genre_tags) LIKE '%rock%' OR LOWER(i.genre_tags) LIKE '%hip-hop%' OR LOWER(i.genre_tags) LIKE '%cricket%' OR LOWER(i.genre_tags) LIKE '%football%' OR LOWER(i.genre_tags) LIKE '%basketball%')")
        elif active_mood == "peaceful":
            where_clauses.append("(LOWER(i.genre_tags) LIKE '%drama%' OR LOWER(i.genre_tags) LIKE '%romance%' OR LOWER(i.genre_tags) LIKE '%classic%' OR LOWER(i.genre_tags) LIKE '%r&b%')")

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # Build HAVING clause for community rating threshold & hidden gems
    having_clauses = []
    if min_rating:
        if min_rating in ("4", "4.0", "4+"):
            having_clauses.append("COALESCE(ROUND(AVG(p.rating), 1), 0) >= 4.0 AND COUNT(p.rating) > 0")
        elif min_rating in ("3", "3.0", "3+"):
            having_clauses.append("COALESCE(ROUND(AVG(p.rating), 1), 0) >= 3.0 AND COUNT(p.rating) > 0")
        elif min_rating in ("2", "2.0", "2+"):
            having_clauses.append("COALESCE(ROUND(AVG(p.rating), 1), 0) >= 2.0 AND COUNT(p.rating) > 0")
        elif min_rating == "unrated":
            having_clauses.append("COUNT(p.rating) = 0")

    if active_mood == "hidden-gem":
        having_clauses.append("COALESCE(ROUND(AVG(p.rating), 1), 0) >= 4.0 AND COUNT(p.rating) BETWEEN 1 AND 5")

    having_sql = ("HAVING " + " AND ".join(having_clauses)) if having_clauses else ""

    # Sorting order logic
    sort_labels = {
        "newest": "Recently Added",
        "highest_rated": "Highest Rated (★)",
        "most_reviewed": "Most Discussed",
        "title_asc": "Title (A → Z)",
        "title_desc": "Title (Z → A)",
        "release_date": "Release Date",
    }

    if active_sort == "highest_rated":
        order_sql = "ORDER BY avg_rating DESC, rating_count DESC, i.id DESC"
    elif active_sort == "most_reviewed":
        order_sql = "ORDER BY rating_count DESC, avg_rating DESC, i.id DESC"
    elif active_sort == "title_asc":
        order_sql = "ORDER BY LOWER(TRIM(i.title)) ASC"
    elif active_sort == "title_desc":
        order_sql = "ORDER BY LOWER(TRIM(i.title)) DESC"
    elif active_sort == "release_date":
        order_sql = "ORDER BY json_extract(i.metadata, '$.release_date') DESC, i.id DESC"
    else:
        active_sort = "newest"
        order_sql = "ORDER BY i.id DESC"

    sql = f"""
        SELECT i.*,
               COALESCE(ROUND(AVG(p.rating), 1), 0) AS avg_rating,
               COUNT(p.rating) AS rating_count
        FROM items i
        LEFT JOIN user_preferences p ON i.id = p.item_id
        {where_sql}
        GROUP BY i.id
        {having_sql}
        {order_sql}
    """
    items = db.execute(sql, params).fetchall()
    items = with_image_urls(items)

    # Attach parsed genre list to each item
    processed_items = []
    for item in items:
        item_dict = dict(item)
        tags_raw = item_dict.get("genre_tags") or ""
        item_dict["parsed_genres"] = [t.strip() for t in tags_raw.split(",") if t.strip()]
        processed_items.append(item_dict)

    user_ratings = {}
    user_collections = []
    recommended_items = []

    if g.user is not None:
        rows = db.execute(
            "SELECT item_id, rating FROM user_preferences WHERE user_id = ?",
            (g.user["id"],),
        ).fetchall()
        user_ratings = {row["item_id"]: row["rating"] for row in rows}

        user_collections = db.execute(
            "SELECT id, title FROM collections WHERE user_id = ? ORDER BY title ASC",
            (g.user["id"],),
        ).fetchall()

        # Compute personalized recommendations for unrated items
        unrated_rows = db.execute(
            """
            SELECT i.*,
                   COALESCE(ROUND(AVG(p.rating), 1), 0) AS avg_rating,
                   COUNT(p.rating) AS rating_count
            FROM items i
            LEFT JOIN user_preferences p ON i.id = p.item_id
            WHERE i.id NOT IN (SELECT item_id FROM user_preferences WHERE user_id = ?)
            GROUP BY i.id
            """,
            (g.user["id"],),
        ).fetchall()

        rec_candidates = []
        for r in unrated_rows:
            pred_score = predict_rating(g.user["id"], r["id"])
            if pred_score >= 3.0:
                rd = dict(r)
                rd["predicted_rating"] = round(pred_score, 1)
                raw_tags = rd.get("genre_tags") or ""
                rd["parsed_genres"] = [t.strip() for t in raw_tags.split(",") if t.strip()]
                rec_candidates.append(rd)
        rec_candidates.sort(key=lambda x: (x["predicted_rating"], x["avg_rating"]), reverse=True)
        recommended_items = with_image_urls(rec_candidates[:6])

    weekly_challenges = get_weekly_challenges(db, g.user["id"] if g.user else None)

    # Query latest movies for the dynamic flash spotlight section (only on default/unfiltered view or movie tab)
    latest_movie_rows = db.execute(
        """
        SELECT i.*,
               COALESCE(ROUND(AVG(p.rating), 1), 0) AS avg_rating,
               COUNT(p.rating) AS rating_count
        FROM items i
        LEFT JOIN user_preferences p ON i.id = p.item_id
        WHERE i.type = 'movie'
        GROUP BY i.id
        ORDER BY i.id DESC
        LIMIT 6
        """
    ).fetchall()

    latest_movies = []
    if latest_movie_rows:
        processed_latest = with_image_urls(latest_movie_rows)
        for row in processed_latest:
            m_dict = dict(row)
            raw_tags = m_dict.get("genre_tags") or ""
            m_dict["parsed_genres"] = [t.strip() for t in raw_tags.split(",") if t.strip()]
            latest_movies.append(m_dict)

    new_movie = latest_movies[0] if latest_movies else None

    # Construct active filter summary chips
    active_chips = []
    if search_query:
        active_chips.append({"key": "q", "label": f'Keyword: "{search_query}"'})
    if item_type:
        active_chips.append({"key": "type", "label": f"Type: {item_type.title()}"})
    if active_genre:
        active_chips.append({"key": "genre", "label": f"Genre: {active_genre.title()}"})
    if min_rating:
        r_lbl = "Unrated" if min_rating == "unrated" else f"★ {min_rating}+"
        active_chips.append({"key": "min_rating", "label": f"Rating: {r_lbl}"})
    if active_era:
        active_chips.append({"key": "era", "label": f"Era: {active_era.upper()}"})
    if active_mood:
        mood_map = {
            "mind-bending": "Atmosphere: 🌌 Mind-Bending",
            "feel-good": "Atmosphere: ☀️ Feel-Good",
            "adrenaline": "Atmosphere: ⚡ Adrenaline",
            "peaceful": "Atmosphere: 🌿 Peaceful",
            "hidden-gem": "Discovery: 💎 Hidden Gems",
        }
        active_chips.append({"key": "mood", "label": mood_map.get(active_mood, f"Mood: {active_mood.title()}")})
    if active_sort and active_sort != "newest":
        active_chips.append({"key": "sort", "label": f"Sort: {sort_labels.get(active_sort, active_sort)}"})

    has_active_filters = bool(search_query or active_genre or min_rating or active_era or active_mood or (active_sort != "newest"))

    return render_template(
        "items.html",
        items=processed_items,
        active_type=item_type,
        search_query=search_query,
        active_genre=active_genre,
        min_rating=min_rating,
        active_sort=active_sort,
        active_era=active_era,
        active_mood=active_mood,
        sort_labels=sort_labels,
        available_genres=available_genres,
        user_ratings=user_ratings,
        user_collections=user_collections,
        recommended_items=recommended_items,
        weekly_challenges=weekly_challenges,
        new_movie=new_movie,
        latest_movies=latest_movies,
        active_chips=active_chips,
        has_active_filters=has_active_filters,
        total_count=len(processed_items),
    )




@bp.route("/<int:item_id>")
def detail(item_id):
    """Dedicated full-page view for a movie, song, or sports team."""
    db = get_db()
    item = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if item is None:
        abort(404)

    item_dict = dict(item)
    item_dict["image_url"] = resolve_image_url(item_dict)
    details = get_item_metadata_and_description(item_dict)

    # Detailed star rating distribution
    rating_stats = db.execute(
        """
        SELECT 
            COALESCE(ROUND(AVG(rating), 1), 0) AS avg_rating,
            COUNT(*) AS rating_count,
            SUM(CASE WHEN rating = 5 THEN 1 ELSE 0 END) AS stars_5,
            SUM(CASE WHEN rating = 4 THEN 1 ELSE 0 END) AS stars_4,
            SUM(CASE WHEN rating = 3 THEN 1 ELSE 0 END) AS stars_3,
            SUM(CASE WHEN rating = 2 THEN 1 ELSE 0 END) AS stars_2,
            SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) AS stars_1
        FROM user_preferences
        WHERE item_id = ?
        """,
        (item_id,),
    ).fetchone()

    # User's own rating & collections
    user_rating = None
    user_collections = []
    if g.user is not None:
        user_pref = db.execute(
            "SELECT rating FROM user_preferences WHERE user_id = ? AND item_id = ?",
            (g.user["id"], item_id),
        ).fetchone()
        if user_pref:
            user_rating = user_pref["rating"]

        user_collections = db.execute(
            "SELECT id, title FROM collections WHERE user_id = ? ORDER BY title ASC",
            (g.user["id"],),
        ).fetchall()

    # Community comments from posts table
    comment_rows = db.execute(
        """
        SELECT p.*, u.username, u.avatar_url, u.role AS user_role
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.item_id = ? OR (p.item_id IS NULL AND LOWER(p.content) LIKE '%' || LOWER(?) || '%')
        ORDER BY p.is_pinned DESC, p.created_at DESC
        """,
        (item_id, item_dict["title"]),
    ).fetchall()

    post_ids = [c["id"] for c in comment_rows]
    comment_reactions = {pid: {"fire": 0, "love": 0, "insightful": 0, "mindblown": 0, "disagree": 0} for pid in post_ids}
    user_comment_reactions = {}
    if post_ids:
        ph = ",".join("?" * len(post_ids))
        reaction_counts = db.execute(
            f"""
            SELECT post_id, reaction, COUNT(*) as c
            FROM post_reactions
            WHERE post_id IN ({ph})
            GROUP BY post_id, reaction
            """,
            post_ids,
        ).fetchall()
        for rc in reaction_counts:
            pid = rc["post_id"]
            rxn = rc["reaction"]
            if pid in comment_reactions and rxn in comment_reactions[pid]:
                comment_reactions[pid][rxn] = rc["c"]

        if g.user is not None:
            user_rxn_rows = db.execute(
                f"""
                SELECT post_id, reaction
                FROM post_reactions
                WHERE user_id = ? AND post_id IN ({ph})
                """,
                [g.user["id"]] + post_ids,
            ).fetchall()
            for ur in user_rxn_rows:
                user_comment_reactions[ur["post_id"]] = ur["reaction"]

    user_badge_cache = {}
    comments = []
    for c in comment_rows:
        cd = dict(c)
        cd["sentiment_label"] = label(cd["sentiment_score"])
        uid = cd["user_id"]
        if uid not in user_badge_cache:
            user_badge_cache[uid] = get_user_badges(db, uid)
        cd["author_badges"] = user_badge_cache[uid]
        cd["reactions"] = comment_reactions.get(cd["id"], {"fire": 0, "love": 0, "insightful": 0, "mindblown": 0, "disagree": 0})
        cd["total_reactions"] = sum(cd["reactions"].values())
        cd["user_reaction"] = user_comment_reactions.get(cd["id"])
        comments.append(cd)

    polarization = detect_polarization(dict(rating_stats) if rating_stats else {})

    # Domain-specific intelligence evaluations
    aspect_ratings = get_movie_aspect_ratings(db, item_id) if item_dict["type"] == "movie" else None
    audience_critic_split = get_movie_audience_vs_critic_split(db, item_id) if item_dict["type"] == "movie" else None
    mood_tags = get_item_mood_tags(db, item_id)
    song_eval = get_song_evaluation_summary(db, item_id) if item_dict["type"] == "song" else None
    quick_reactions = get_item_quick_reactions(db, item_id, g.user["id"] if g.user else None)
    match_summary = get_sports_match_summary(db, item_id) if item_dict["type"] == "team" else None
    match_highlights = get_sports_highlight_votes(db, item_id) if item_dict["type"] == "team" else None
    match_predictions = get_sports_predictions_summary(db, item_id, g.user["id"] if g.user else None) if item_dict["type"] == "team" else None

    user_aspects = None
    user_song_eval = None
    user_match_rating = None
    if g.user is not None:
        if item_dict["type"] == "movie":
            u_asp = db.execute("SELECT * FROM movie_aspect_ratings WHERE item_id = ? AND user_id = ?", (item_id, g.user["id"])).fetchone()
            if u_asp:
                user_aspects = dict(u_asp)
        elif item_dict["type"] == "song":
            u_se = db.execute("SELECT * FROM song_evaluations WHERE item_id = ? AND user_id = ?", (item_id, g.user["id"])).fetchone()
            if u_se:
                user_song_eval = dict(u_se)
        elif item_dict["type"] == "team":
            u_mr = db.execute("SELECT * FROM sports_match_ratings WHERE item_id = ? AND user_id = ?", (item_id, g.user["id"])).fetchone()
            if u_mr:
                user_match_rating = dict(u_mr)

    # Related items of the same type
    related_rows = db.execute(
        """
        SELECT i.*, COALESCE(ROUND(AVG(p.rating), 1), 0) AS avg_rating, COUNT(p.rating) AS rating_count
        FROM items i
        LEFT JOIN user_preferences p ON i.id = p.item_id
        WHERE i.type = ? AND i.id != ?
        GROUP BY i.id
        ORDER BY avg_rating DESC, rating_count DESC
        LIMIT 4
        """,
        (item_dict["type"], item_id),
    ).fetchall()
    related_items = with_image_urls(related_rows)
    trailer_info = resolve_movie_trailer(item_dict, db=db) if item_dict["type"] == "movie" else None

    return render_template(
        "item_detail.html",
        item=item_dict,
        details=details,
        stats=dict(rating_stats) if rating_stats else {},
        polarization=polarization,
        aspect_ratings=aspect_ratings,
        audience_critic_split=audience_critic_split,
        mood_tags=mood_tags,
        preset_movie_moods=PRESET_MOVIE_MOODS,
        song_eval=song_eval,
        quick_reactions=quick_reactions,
        reaction_meta=QUICK_REACTION_META,
        match_summary=match_summary,
        match_highlights=match_highlights,
        highlight_meta=HIGHLIGHT_TYPE_META,
        match_predictions=match_predictions,
        user_aspects=user_aspects,
        user_song_eval=user_song_eval,
        user_match_rating=user_match_rating,
        user_rating=user_rating,
        user_collections=user_collections,
        comments=comments,
        related_items=related_items,
        trailer=trailer_info,
    )


@bp.route("/<int:item_id>/trailer")
def item_trailer(item_id):
    """JSON API endpoint returning trailer embed data for a movie item."""
    db = get_db()
    item = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if item is None or item["type"] != "movie":
        return jsonify({"success": False, "error": "Movie not found"}), 404

    item_dict = dict(item)
    trailer_info = resolve_movie_trailer(item_dict, db=db)
    return jsonify({
        "success": True,
        "item_id": item["id"],
        "title": item["title"],
        "trailer": trailer_info,
    })


@bp.route("/<int:item_id>/quick-view")
def quick_view(item_id):
    """JSON API endpoint for interactive modal quick-view from catalog banners and cards."""
    db = get_db()
    item = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if item is None:
        return jsonify({"error": "Item not found"}), 404

    item_dict = dict(item)
    item_dict["image_url"] = resolve_image_url(item_dict)
    details = get_item_metadata_and_description(item_dict)
    trailer_info = resolve_movie_trailer(item_dict, db=db) if item_dict["type"] == "movie" else None

    rating_stats = db.execute(
        """
        SELECT 
            COALESCE(ROUND(AVG(rating), 1), 0) AS avg_rating,
            COUNT(*) AS rating_count,
            SUM(CASE WHEN rating = 5 THEN 1 ELSE 0 END) AS stars_5,
            SUM(CASE WHEN rating = 4 THEN 1 ELSE 0 END) AS stars_4,
            SUM(CASE WHEN rating = 3 THEN 1 ELSE 0 END) AS stars_3,
            SUM(CASE WHEN rating = 2 THEN 1 ELSE 0 END) AS stars_2,
            SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) AS stars_1
        FROM user_preferences
        WHERE item_id = ?
        """,
        (item_id,),
    ).fetchone()

    polarization = detect_polarization(dict(rating_stats) if rating_stats else {})

    user_rating = None
    if g.user is not None:
        user_pref = db.execute(
            "SELECT rating FROM user_preferences WHERE user_id = ? AND item_id = ?",
            (g.user["id"], item_id),
        ).fetchone()
        if user_pref:
            user_rating = user_pref["rating"]

    comment_rows = db.execute(
        """
        SELECT p.id, p.content, p.sentiment_score, p.created_at, p.is_pinned,
               u.username, u.avatar_url, u.role AS user_role
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.item_id = ?
        ORDER BY p.is_pinned DESC, p.created_at DESC
        LIMIT 30
        """,
        (item_id,),
    ).fetchall()

    comments = []
    for c in comment_rows:
        cd = dict(c)
        cd["sentiment_label"] = label(cd["sentiment_score"])
        cd["created_at_fmt"] = cd["created_at"][:16] if cd.get("created_at") else ""
        comments.append(cd)

    return jsonify({
        "id": item_dict["id"],
        "title": item_dict["title"],
        "type": item_dict["type"],
        "image_url": item_dict["image_url"],
        "description": details["description"],
        "genres": details["genres"],
        "release_date": details["release_date"],
        "vote_average": details["vote_average"],
        "director": details["director"],
        "cast": details["cast"],
        "artist": details["artist"],
        "album": details["album"],
        "runtime": details["runtime"],
        "vibe": details["vibe"],
        "themes": details["themes"],
        "avg_rating": rating_stats["avg_rating"] if rating_stats else 0,
        "rating_count": rating_stats["rating_count"] if rating_stats else 0,
        "polarization": polarization,
        "user_rating": user_rating,
        "trailer": trailer_info,
        "comments": comments,
        "is_logged_in": g.user is not None,
    })


@bp.route("/<int:item_id>/comment", methods=["POST"])
@login_required
def add_comment(item_id):
    """Submit a community comment/review on a movie, song, or team."""
    db = get_db()
    item = db.execute("SELECT id, title, type FROM items WHERE id = ?", (item_id,)).fetchone()
    if item is None:
        abort(404)

    is_ajax = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if request.is_json:
        data = request.get_json() or {}
        content = data.get("content", "").strip()
        is_spoiler = 1 if (data.get("is_spoiler") in ("1", "true", "on", True, 1)) else 0
        spoiler_warning = data.get("spoiler_warning", "").strip()
    else:
        content = request.form.get("content", "").strip()
        is_spoiler = 1 if request.form.get("is_spoiler") in ("1", "true", "on", True, 1) else 0
        spoiler_warning = request.form.get("spoiler_warning", "").strip()

    if not content:
        if is_ajax:
            return jsonify({"success": False, "error": "Comment cannot be empty."}), 400
        flash("Comment cannot be empty.")
        return redirect(url_for("items.detail", item_id=item_id))

    score = analyze(content)
    sentiment_text = label(score)

    cursor = db.execute(
        "INSERT INTO posts (user_id, item_id, content, sentiment_score, is_spoiler, spoiler_warning) VALUES (?, ?, ?, ?, ?, ?)",
        (g.user["id"], item_id, content, score, is_spoiler, spoiler_warning),
    )
    db.commit()
    new_post_id = cursor.lastrowid

    if is_ajax:
        return jsonify({
            "success": True,
            "comment": {
                "id": new_post_id,
                "content": content,
                "sentiment_score": score,
                "sentiment_label": sentiment_text,
                "is_spoiler": is_spoiler,
                "spoiler_warning": spoiler_warning,
                "username": g.user["username"],
                "avatar_url": dict(g.user).get("avatar_url") or "",
                "created_at_fmt": "Just now",
            }
        })

    flash(f"Your comment on '{item['title']}' was posted! (Sentiment: {sentiment_text})")
    return redirect(url_for("items.detail", item_id=item_id))


@bp.route("/<int:item_id>/rate", methods=["POST"])
@login_required
def rate(item_id):
    rating = int(request.form.get("rating") or (request.json and request.json.get("rating")) or 0)
    is_ajax = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if rating < 1 or rating > 5:
        if is_ajax:
            return jsonify({"success": False, "error": "Rating must be between 1 and 5."}), 400
        flash("Rating must be between 1 and 5.")
        return redirect(url_for("items.browse"))

    db = get_db()
    db.execute(
        """
        INSERT INTO user_preferences (user_id, item_id, rating)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, item_id) DO UPDATE SET rating = excluded.rating
        """,
        (g.user["id"], item_id, rating),
    )
    db.commit()

    if is_ajax:
        new_stats = db.execute(
            "SELECT COALESCE(ROUND(AVG(rating), 1), 0) AS avg_rating, COUNT(*) AS rating_count FROM user_preferences WHERE item_id = ?",
            (item_id,),
        ).fetchone()
        return jsonify({
            "success": True,
            "user_rating": rating,
            "avg_rating": new_stats["avg_rating"],
            "rating_count": new_stats["rating_count"],
        })

    return redirect(request.referrer or url_for("items.detail", item_id=item_id))


@bp.route("/<int:item_id>/submit-review", methods=["POST"])
def submit_review(item_id):
    """
    Unified endpoint to submit both star rating and written review with a soothing UI.
    Works seamlessly via AJAX JSON or standard HTML form submission.
    """
    is_ajax = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if g.user is None:
        if is_ajax:
            return jsonify({"success": False, "error": "Please log in to submit a review."}), 401
        flash("Please log in to review this movie.")
        return redirect(url_for("auth.login"))

    db = get_db()
    item = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if item is None:
        abort(404)

    if request.is_json:
        data = request.get_json() or {}
        rating = int(data.get("rating", 0) or 0)
        content = (data.get("content") or "").strip()
        vibe_tag = (data.get("vibe_tag") or "").strip()
        is_spoiler = 1 if (data.get("is_spoiler") in ("1", "true", "on", True, 1)) else 0
        spoiler_warning = (data.get("spoiler_warning") or "").strip()
    else:
        rating = int(request.form.get("rating", 0) or 0)
        content = (request.form.get("content") or "").strip()
        vibe_tag = (request.form.get("vibe_tag") or "").strip()
        is_spoiler = 1 if request.form.get("is_spoiler") in ("1", "true", "on", True, 1) else 0
        spoiler_warning = (request.form.get("spoiler_warning") or "").strip()

    if rating < 1 or rating > 5:
        msg = "Please select a peaceful star rating between 1 and 5."
        if is_ajax:
            return jsonify({"success": False, "error": msg}), 400
        flash(msg)
        return redirect(url_for("items.detail", item_id=item_id))

    # 1. Upsert rating in user_preferences
    db.execute(
        """
        INSERT INTO user_preferences (user_id, item_id, rating)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, item_id) DO UPDATE SET rating = excluded.rating
        """,
        (g.user["id"], item_id, rating),
    )

    # 2. Insert review if content provided
    new_post_id = None
    score = 0.0
    sentiment_text = "Mindful & Positive"
    full_content = ""
    if content:
        full_content = f"[{vibe_tag}] {content}" if (vibe_tag and not content.startswith(f"[{vibe_tag}]")) else content
        score = analyze(full_content)
        sentiment_text = label(score)
        cursor = db.execute(
            """
            INSERT INTO posts (user_id, item_id, content, sentiment_score, is_spoiler, spoiler_warning)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (g.user["id"], item_id, full_content, score, is_spoiler, spoiler_warning),
        )
        new_post_id = cursor.lastrowid

    db.commit()

    # Query fresh rating stats
    new_stats = db.execute(
        """
        SELECT COALESCE(ROUND(AVG(rating), 1), 0) AS avg_rating,
               COUNT(*) AS rating_count
        FROM user_preferences
        WHERE item_id = ?
        """,
        (item_id,),
    ).fetchone()

    if is_ajax:
        return jsonify({
            "success": True,
            "message": f"Your peaceful review for '{item['title']}' has been recorded!",
            "user_rating": rating,
            "avg_rating": new_stats["avg_rating"],
            "rating_count": new_stats["rating_count"],
            "comment": {
                "id": new_post_id,
                "content": full_content if content else "",
                "vibe_tag": vibe_tag,
                "sentiment_score": score,
                "sentiment_label": sentiment_text,
                "is_spoiler": is_spoiler,
                "spoiler_warning": spoiler_warning,
                "username": g.user["username"],
                "avatar_url": dict(g.user).get("avatar_url") or "",
                "created_at_fmt": "Just now",
            } if new_post_id else None
        })

    flash(f"Your peaceful review for '{item['title']}' has been recorded! (Sentiment: {sentiment_text})")
    return redirect(url_for("items.detail", item_id=item_id))


# ===========================================================================
# DEDICATED DOMAIN SECTIONS (MOVIES, SONGS, SPORTS)
# ===========================================================================

@bp.route("/movies")
def movies_hub():
    """Redirect to unified catalog filtered by movies."""
    return redirect(url_for("items.browse", type="movie"))


@bp.route("/songs")
def songs_hub():
    """Redirect to unified catalog filtered by music."""
    return redirect(url_for("items.browse", type="song"))


@bp.route("/sports")
def sports_hub():
    """Redirect to unified catalog filtered by sports."""
    return redirect(url_for("items.browse", type="team"))


# ===========================================================================
# INTERACTIVE DOMAIN RATING & SOCIAL ENDPOINTS
# ===========================================================================

@bp.route("/<int:item_id>/rate-aspects", methods=["POST"])
@login_required
def rate_aspects(item_id):
    """Save 5-criteria aspect rating for a movie: storyline, acting, direction, cinematography, music."""
    db = get_db()
    data = request.get_json() if request.is_json else request.form
    storyline = int(data.get("storyline", 5))
    acting = int(data.get("acting", 5))
    direction = int(data.get("direction", 5))
    cinematography = int(data.get("cinematography", 5))
    music = int(data.get("music", 5))

    db.execute(
        """
        INSERT INTO movie_aspect_ratings (user_id, item_id, storyline, acting, direction, cinematography, music)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, item_id) DO UPDATE SET
            storyline = excluded.storyline,
            acting = excluded.acting,
            direction = excluded.direction,
            cinematography = excluded.cinematography,
            music = excluded.music
        """,
        (g.user["id"], item_id, storyline, acting, direction, cinematography, music),
    )
    db.commit()

    aspects = get_movie_aspect_ratings(db, item_id)
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True, "aspects": aspects})
    flash("Cinematic aspect ratings saved successfully!")
    return redirect(request.referrer or url_for("items.detail", item_id=item_id))


@bp.route("/<int:item_id>/mood-tag", methods=["POST"])
@login_required
def add_mood_tag(item_id):
    """Tag an item or movie with a community mood."""
    db = get_db()
    data = request.get_json() if request.is_json else request.form
    mood = (data.get("mood") or "").strip().lower()
    if not mood:
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": False, "error": "Mood tag cannot be empty."}), 400
        return redirect(request.referrer or url_for("items.detail", item_id=item_id))

    db.execute(
        """
        INSERT OR IGNORE INTO item_mood_tags (item_id, user_id, mood)
        VALUES (?, ?, ?)
        """,
        (item_id, g.user["id"], mood),
    )
    db.commit()

    tags = get_item_mood_tags(db, item_id)
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True, "mood_tags": tags})
    flash(f"Tagged movie with mood '{mood.title()}'!")
    return redirect(request.referrer or url_for("items.detail", item_id=item_id))


@bp.route("/<int:item_id>/evaluate-song", methods=["POST"])
@login_required
def evaluate_song(item_id):
    """Save emotion, replay value, and lyrics vs. music split ratings for a song."""
    db = get_db()
    data = request.get_json() if request.is_json else request.form
    emotion = data.get("emotion") or "chill"
    replay_val = int(data.get("replay_value", 4))
    lyrics = int(data.get("lyrics_score", 4))
    music = int(data.get("music_score", 4))

    db.execute(
        """
        INSERT INTO song_evaluations (user_id, item_id, emotion, replay_value, lyrics_score, music_score)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, item_id) DO UPDATE SET
            emotion = excluded.emotion,
            replay_value = excluded.replay_value,
            lyrics_score = excluded.lyrics_score,
            music_score = excluded.music_score
        """,
        (g.user["id"], item_id, emotion, replay_val, lyrics, music),
    )
    db.commit()

    summary = get_song_evaluation_summary(db, item_id)
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True, "summary": summary})
    flash("Song evaluation saved!")
    return redirect(request.referrer or url_for("items.detail", item_id=item_id))


@bp.route("/<int:item_id>/quick-react", methods=["POST"])
@login_required
def quick_react(item_id):
    """Toggle 1-click emoji reaction on a catalog item or song (fire, love, vibe, energetic, masterpiece)."""
    db = get_db()
    data = request.get_json() if request.is_json else request.form
    reaction = data.get("reaction") or "fire"

    existing = db.execute(
        "SELECT id FROM item_quick_reactions WHERE item_id = ? AND user_id = ? AND reaction = ?",
        (item_id, g.user["id"], reaction),
    ).fetchone()

    if existing:
        db.execute("DELETE FROM item_quick_reactions WHERE id = ?", (existing["id"],))
    else:
        db.execute(
            """
            INSERT OR REPLACE INTO item_quick_reactions (user_id, item_id, reaction)
            VALUES (?, ?, ?)
            """,
            (g.user["id"], item_id, reaction),
        )
    db.commit()

    reactions = get_item_quick_reactions(db, item_id, g.user["id"])
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True, "reactions": reactions})
    return redirect(request.referrer or url_for("items.detail", item_id=item_id))


@bp.route("/<int:item_id>/rate-match", methods=["POST"])
@login_required
def rate_match(item_id):
    """Rate match excitement index: thrill level, competitiveness, memorable moments."""
    db = get_db()
    data = request.get_json() if request.is_json else request.form
    thrill = int(data.get("thrill_level", 4))
    comp = int(data.get("competitiveness", 4))
    mem = int(data.get("memorable_moments", 4))

    db.execute(
        """
        INSERT INTO sports_match_ratings (user_id, item_id, thrill_level, competitiveness, memorable_moments)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, item_id) DO UPDATE SET
            thrill_level = excluded.thrill_level,
            competitiveness = excluded.competitiveness,
            memorable_moments = excluded.memorable_moments
        """,
        (g.user["id"], item_id, thrill, comp, mem),
    )
    db.commit()

    summary = get_sports_match_summary(db, item_id)
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True, "summary": summary})
    flash("Match excitement rating submitted!")
    return redirect(request.referrer or url_for("items.detail", item_id=item_id))


@bp.route("/<int:item_id>/predict", methods=["POST"])
@login_required
def submit_prediction(item_id):
    """Submit match outcome prediction to earn credibility points and accuracy score."""
    db = get_db()
    data = request.get_json() if request.is_json else request.form
    predicted_outcome = data.get("predicted_outcome", "Home Win")
    confidence_points = int(data.get("confidence_points", 10))

    db.execute(
        """
        INSERT INTO sports_predictions (user_id, item_id, predicted_outcome, confidence_points, points_awarded)
        VALUES (?, ?, ?, ?, 10)
        ON CONFLICT(user_id, item_id) DO UPDATE SET
            predicted_outcome = excluded.predicted_outcome,
            confidence_points = excluded.confidence_points
        """,
        (g.user["id"], item_id, predicted_outcome, confidence_points),
    )
    db.commit()

    summary = get_sports_predictions_summary(db, item_id, g.user["id"])
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True, "predictions": summary})
    flash("Match prediction locked in!")
    return redirect(request.referrer or url_for("items.browse", type="team"))


@bp.route("/<int:item_id>/vote-highlight", methods=["POST"])
@login_required
def vote_highlight(item_id):
    """Vote for match highlight (Best Play, Turning Point, Clutch Moment)."""
    db = get_db()
    data = request.get_json() if request.is_json else request.form
    highlight_type = data.get("highlight_type", "best_play")
    title = (data.get("highlight_title") or "Match Highlight").strip()

    db.execute(
        """
        INSERT INTO sports_highlight_votes (user_id, item_id, highlight_type, highlight_title)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, item_id, highlight_type) DO UPDATE SET
            highlight_title = excluded.highlight_title
        """,
        (g.user["id"], item_id, highlight_type, title),
    )
    db.commit()

    highlights = get_sports_highlight_votes(db, item_id)
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True, "highlights": highlights})
    flash("Highlight vote recorded!")
    return redirect(request.referrer or url_for("items.detail", item_id=item_id))


@bp.route("/<int:item_id>/rate-player", methods=["POST"])
@login_required
def rate_player(item_id):
    """Rate individual standout player performance (1-10) and nominate match MVP."""
    db = get_db()
    data = request.get_json() if request.is_json else request.form
    player_name = (data.get("player_name") or "").strip()
    rating = int(data.get("rating", 8))
    is_mvp = 1 if data.get("is_mvp") in ("1", "true", "on", True, 1) else 0

    if not player_name:
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": False, "error": "Player name required."}), 400
        return redirect(request.referrer or url_for("items.detail", item_id=item_id))

    db.execute(
        """
        INSERT INTO sports_player_ratings (user_id, item_id, player_name, rating, is_mvp)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, item_id, player_name) DO UPDATE SET
            rating = excluded.rating,
            is_mvp = excluded.is_mvp
        """,
        (g.user["id"], item_id, player_name, rating, is_mvp),
    )
    db.commit()

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True, "player_name": player_name, "rating": rating})
    flash(f"Performance rating for '{player_name}' saved!")
    return redirect(request.referrer or url_for("items.detail", item_id=item_id))


