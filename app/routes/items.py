from flask import Blueprint, render_template, request, redirect, url_for, g, flash

from app.db import get_db
from app.auth_utils import login_required
from app.services.item_media import with_image_urls

bp = Blueprint("items", __name__, url_prefix="/items")


@bp.route("/")
def browse():
    """Browse items, optionally filtered by type (movie | song | team) and genre."""
    item_type = request.args.get("type", "").strip().lower()
    if item_type not in ("movie", "song", "team"):
        item_type = None

    active_genre = request.args.get("genre", "").strip().lower()
    db = get_db()

    # Query distinct genre tags for the active type filter
    if item_type:
        tag_rows = db.execute(
            "SELECT genre_tags FROM items WHERE type = ? AND genre_tags IS NOT NULL AND genre_tags != ''",
            (item_type,),
        ).fetchall()
    else:
        tag_rows = db.execute(
            "SELECT genre_tags FROM items WHERE genre_tags IS NOT NULL AND genre_tags != ''"
        ).fetchall()

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

    # Build SQL query with optional type and genre filtering
    where_clauses = []
    params = []

    if item_type:
        where_clauses.append("i.type = ?")
        params.append(item_type)

    if active_genre:
        where_clauses.append("(',' || LOWER(REPLACE(i.genre_tags, ' ', '')) || ',') LIKE ?")
        params.append(f"%,{active_genre.replace(' ', '')},%")

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    order_sql = "ORDER BY i.title" if item_type else "ORDER BY i.type, i.title"

    sql = f"""
        SELECT i.*,
               COALESCE(ROUND(AVG(p.rating), 1), 0) AS avg_rating,
               COUNT(p.rating) AS rating_count
        FROM items i
        LEFT JOIN user_preferences p ON i.id = p.item_id
        {where_sql}
        GROUP BY i.id
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

    return render_template(
        "items.html",
        items=processed_items,
        active_type=item_type,
        active_genre=active_genre,
        available_genres=available_genres,
        user_ratings=user_ratings,
        user_collections=user_collections,
    )


@bp.route("/<int:item_id>/rate", methods=["POST"])
@login_required
def rate(item_id):
    rating = int(request.form["rating"])
    if rating < 1 or rating > 5:
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
    return redirect(request.referrer or url_for("items.browse"))
