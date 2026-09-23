import json
from flask import Blueprint, render_template, request, redirect, url_for, g, flash, jsonify, abort

from app.db import get_db
from app.auth_utils import login_required
from app.services.item_media import with_image_urls, resolve_image_url
from app.services.sentiment import analyze, label
from app.services.movie_agent import MOVIE_KNOWLEDGE_BASE, SONG_KNOWLEDGE_BASE

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

    # Build SQL query with optional type, genre, search, and era filtering
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

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # Build HAVING clause for community rating threshold
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
    if active_sort and active_sort != "newest":
        active_chips.append({"key": "sort", "label": f"Sort: {sort_labels.get(active_sort, active_sort)}"})

    has_active_filters = bool(search_query or active_genre or min_rating or active_era or (active_sort != "newest"))

    return render_template(
        "items.html",
        items=processed_items,
        active_type=item_type,
        search_query=search_query,
        active_genre=active_genre,
        min_rating=min_rating,
        active_sort=active_sort,
        active_era=active_era,
        sort_labels=sort_labels,
        available_genres=available_genres,
        user_ratings=user_ratings,
        user_collections=user_collections,
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

    comments = []
    for c in comment_rows:
        cd = dict(c)
        cd["sentiment_label"] = label(cd["sentiment_score"])
        comments.append(cd)

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

    return render_template(
        "item_detail.html",
        item=item_dict,
        details=details,
        stats=dict(rating_stats) if rating_stats else {},
        user_rating=user_rating,
        user_collections=user_collections,
        comments=comments,
        related_items=related_items,
    )


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

    rating_stats = db.execute(
        """
        SELECT 
            COALESCE(ROUND(AVG(rating), 1), 0) AS avg_rating,
            COUNT(*) AS rating_count
        FROM user_preferences
        WHERE item_id = ?
        """,
        (item_id,),
    ).fetchone()

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
        "user_rating": user_rating,
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
    else:
        content = request.form.get("content", "").strip()

    if not content:
        if is_ajax:
            return jsonify({"success": False, "error": "Comment cannot be empty."}), 400
        flash("Comment cannot be empty.")
        return redirect(url_for("items.detail", item_id=item_id))

    score = analyze(content)
    sentiment_text = label(score)

    cursor = db.execute(
        "INSERT INTO posts (user_id, item_id, content, sentiment_score) VALUES (?, ?, ?, ?)",
        (g.user["id"], item_id, content, score),
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

