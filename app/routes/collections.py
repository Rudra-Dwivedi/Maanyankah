import json
from flask import Blueprint, render_template, request, redirect, url_for, g, flash, abort, jsonify

from app.db import get_db
from app.auth_utils import login_required
from app.services.item_media import with_image_urls

bp = Blueprint("collections", __name__, url_prefix="/collections")


def _get_collection_preview_images(db, collection_ids):
    """Return a dict mapping collection_id -> list of up to 4 item image URLs."""
    if not collection_ids:
        return {}
    
    placeholders = ",".join("?" * len(collection_ids))
    rows = db.execute(
        f"""
        SELECT ci.collection_id, i.metadata
        FROM collection_items ci
        JOIN items i ON ci.item_id = i.id
        WHERE ci.collection_id IN ({placeholders})
        ORDER BY ci.added_at DESC
        """,
        collection_ids,
    ).fetchall()

    previews = {cid: [] for cid in collection_ids}
    for r in rows:
        cid = r["collection_id"]
        if len(previews[cid]) < 4:
            meta = {}
            if r["metadata"]:
                try:
                    meta = json.loads(r["metadata"])
                except Exception:
                    pass
            img = meta.get("image_url") or meta.get("poster_url") or meta.get("album_art")
            if img and img not in previews[cid]:
                previews[cid].append(img)
    return previews


@bp.route("/")
def index():
    """Browse community collections and user's own collections."""
    db = get_db()
    tab = request.args.get("tab", "explore").lower()

    # Public community collections
    public_collections = db.execute(
        """
        SELECT c.*,
               u.username, u.avatar_url,
               COUNT(ci.id) AS item_count,
               SUM(CASE WHEN i.type = 'movie' THEN 1 ELSE 0 END) AS movie_count,
               SUM(CASE WHEN i.type = 'song' THEN 1 ELSE 0 END) AS song_count
        FROM collections c
        JOIN users u ON c.user_id = u.id
        LEFT JOIN collection_items ci ON c.id = ci.collection_id
        LEFT JOIN items i ON ci.item_id = i.id
        WHERE c.is_public = 1
        GROUP BY c.id
        ORDER BY c.updated_at DESC
        """
    ).fetchall()

    my_collections = []
    if g.user is not None:
        my_collections = db.execute(
            """
            SELECT c.*,
                   u.username, u.avatar_url,
                   COUNT(ci.id) AS item_count,
                   SUM(CASE WHEN i.type = 'movie' THEN 1 ELSE 0 END) AS movie_count,
                   SUM(CASE WHEN i.type = 'song' THEN 1 ELSE 0 END) AS song_count
            FROM collections c
            JOIN users u ON c.user_id = u.id
            LEFT JOIN collection_items ci ON c.id = ci.collection_id
            LEFT JOIN items i ON ci.item_id = i.id
            WHERE c.user_id = ?
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            """,
            (g.user["id"],),
        ).fetchall()

    # Fetch preview images for all collections
    all_cids = list({c["id"] for c in public_collections} | {c["id"] for c in my_collections})
    previews = _get_collection_preview_images(db, all_cids)

    return render_template(
        "collections.html",
        public_collections=public_collections,
        my_collections=my_collections,
        previews=previews,
        active_tab=tab,
    )


@bp.route("/create", methods=["POST"])
@login_required
def create():
    """Create a new collection."""
    is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if is_json and request.is_json:
        data = request.get_json() or {}
        title = data.get("title", "").strip()
        desc = data.get("description", "").strip()
        is_public = 1 if data.get("is_public", True) else 0
        initial_item_id = data.get("initial_item_id")
    else:
        title = request.form.get("title", "").strip()
        desc = request.form.get("description", "").strip()
        is_public = 1 if request.form.get("is_public") in ("1", "on", "true", True) else 0
        initial_item_id = request.form.get("initial_item_id", type=int)

    if not title:
        if is_json:
            return jsonify({"success": False, "error": "Title is required"}), 400
        flash("Collection title is required.")
        return redirect(url_for("collections.index"))

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO collections (user_id, title, description, is_public) VALUES (?, ?, ?, ?)",
        (g.user["id"], title, desc, is_public),
    )
    new_cid = cursor.lastrowid

    if initial_item_id:
        cursor.execute(
            "INSERT OR IGNORE INTO collection_items (collection_id, item_id) VALUES (?, ?)",
            (new_cid, initial_item_id),
        )

    db.commit()

    if is_json:
        return jsonify({
            "success": True,
            "collection": {
                "id": new_cid,
                "title": title,
                "is_public": is_public,
                "item_count": 1 if initial_item_id else 0,
            },
            "message": f"Collection '{title}' created successfully!",
        })

    flash(f"Collection '{title}' created!")
    return redirect(url_for("collections.detail", collection_id=new_cid))


@bp.route("/<int:collection_id>")
def detail(collection_id):
    """View details and items inside a collection."""
    db = get_db()
    collection = db.execute(
        """
        SELECT c.*, u.username, u.avatar_url, u.role as creator_role
        FROM collections c
        JOIN users u ON c.user_id = u.id
        WHERE c.id = ?
        """,
        (collection_id,),
    ).fetchone()

    if collection is None:
        abort(404)

    is_owner = g.user is not None and (g.user["id"] == collection["user_id"] or g.user["role"] == "admin")

    # Private collection check
    if not collection["is_public"] and not is_owner:
        abort(403)

    # Fetch items in collection
    items = db.execute(
        """
        SELECT i.*,
               ci.note,
               ci.added_at,
               COALESCE(ROUND(AVG(p.rating), 1), 0) AS avg_rating,
               COUNT(p.rating) AS rating_count
        FROM collection_items ci
        JOIN items i ON ci.item_id = i.id
        LEFT JOIN user_preferences p ON i.id = p.item_id
        WHERE ci.collection_id = ?
        GROUP BY i.id
        ORDER BY ci.added_at DESC
        """,
        (collection_id,),
    ).fetchall()

    items = with_image_urls(items)

    # Attach parsed genre list
    processed_items = []
    for it in items:
        d = dict(it)
        raw_tags = d.get("genre_tags") or ""
        d["parsed_genres"] = [t.strip() for t in raw_tags.split(",") if t.strip()]
        processed_items.append(d)

    # User ratings map
    user_ratings = {}
    if g.user is not None:
        rows = db.execute(
            "SELECT item_id, rating FROM user_preferences WHERE user_id = ?",
            (g.user["id"],),
        ).fetchall()
        user_ratings = {r["item_id"]: r["rating"] for r in rows}

    # If owner, fetch catalog items not yet in collection for quick search & add
    catalog_items = []
    if is_owner:
        existing_ids = [it["id"] for it in processed_items]
        if existing_ids:
            ph = ",".join("?" * len(existing_ids))
            catalog_items = db.execute(
                f"SELECT id, type, title, genre_tags, metadata FROM items WHERE id NOT IN ({ph}) ORDER BY title ASC",
                existing_ids,
            ).fetchall()
        else:
            catalog_items = db.execute(
                "SELECT id, type, title, genre_tags, metadata FROM items ORDER BY title ASC"
            ).fetchall()
        catalog_items = with_image_urls(catalog_items)

    movie_count = sum(1 for it in processed_items if it["type"] == "movie")
    song_count = sum(1 for it in processed_items if it["type"] == "song")

    return render_template(
        "collection_detail.html",
        collection=collection,
        items=processed_items,
        is_owner=is_owner,
        user_ratings=user_ratings,
        catalog_items=catalog_items,
        movie_count=movie_count,
        song_count=song_count,
    )


@bp.route("/<int:collection_id>/items/add", methods=["POST"])
@login_required
def add_item(collection_id):
    """Add an item to a collection."""
    db = get_db()
    collection = db.execute("SELECT * FROM collections WHERE id = ?", (collection_id,)).fetchone()
    if collection is None:
        abort(404)
    if collection["user_id"] != g.user["id"] and g.user["role"] != "admin":
        abort(403)

    is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if is_json and request.is_json:
        data = request.get_json() or {}
        item_id = data.get("item_id")
        note = data.get("note", "").strip()
    else:
        item_id = request.form.get("item_id", type=int)
        note = request.form.get("note", "").strip()

    if not item_id:
        if is_json:
            return jsonify({"success": False, "error": "Item ID required"}), 400
        flash("Item is required.")
        return redirect(url_for("collections.detail", collection_id=collection_id))

    db.execute(
        """
        INSERT INTO collection_items (collection_id, item_id, note)
        VALUES (?, ?, ?)
        ON CONFLICT(collection_id, item_id) DO UPDATE SET note = excluded.note
        """,
        (collection_id, item_id, note or None),
    )
    db.execute("UPDATE collections SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (collection_id,))
    db.commit()

    if is_json:
        return jsonify({"success": True, "message": "Item added to collection!"})

    flash("Item added to collection!")
    return redirect(url_for("collections.detail", collection_id=collection_id))


@bp.route("/<int:collection_id>/items/<int:item_id>/remove", methods=["POST"])
@login_required
def remove_item(collection_id, item_id):
    """Remove an item from a collection."""
    db = get_db()
    collection = db.execute("SELECT * FROM collections WHERE id = ?", (collection_id,)).fetchone()
    if collection is None:
        abort(404)
    if collection["user_id"] != g.user["id"] and g.user["role"] != "admin":
        abort(403)

    db.execute(
        "DELETE FROM collection_items WHERE collection_id = ? AND item_id = ?",
        (collection_id, item_id),
    )
    db.execute("UPDATE collections SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (collection_id,))
    db.commit()

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True, "message": "Item removed from collection!"})

    flash("Item removed from collection.")
    return redirect(url_for("collections.detail", collection_id=collection_id))


@bp.route("/<int:collection_id>/edit", methods=["POST"])
@login_required
def edit(collection_id):
    """Edit collection metadata (title, description, visibility)."""
    db = get_db()
    collection = db.execute("SELECT * FROM collections WHERE id = ?", (collection_id,)).fetchone()
    if collection is None:
        abort(404)
    if collection["user_id"] != g.user["id"] and g.user["role"] != "admin":
        abort(403)

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    is_public = 1 if request.form.get("is_public") in ("1", "on", "true", True) else 0

    if not title:
        flash("Title is required.")
        return redirect(url_for("collections.detail", collection_id=collection_id))

    db.execute(
        """
        UPDATE collections
        SET title = ?, description = ?, is_public = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (title, description, is_public, collection_id),
    )
    db.commit()
    flash("Collection updated!")
    return redirect(url_for("collections.detail", collection_id=collection_id))


@bp.route("/<int:collection_id>/delete", methods=["POST"])
@login_required
def delete(collection_id):
    """Delete a collection."""
    db = get_db()
    collection = db.execute("SELECT * FROM collections WHERE id = ?", (collection_id,)).fetchone()
    if collection is None:
        abort(404)
    if collection["user_id"] != g.user["id"] and g.user["role"] != "admin":
        abort(403)

    title = collection["title"]
    db.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
    db.commit()

    flash(f"Collection '{title}' has been deleted.")
    return redirect(url_for("collections.index"))


# =========================================================================
# AJAX API Endpoints for Quick Add-to-Collection Modal
# =========================================================================

@bp.route("/api/user-collections")
@login_required
def api_user_collections():
    """Return JSON list of current user's collections with item presence flag."""
    item_id = request.args.get("item_id", type=int)
    db = get_db()

    rows = db.execute(
        """
        SELECT c.id, c.title, c.is_public,
               COUNT(ci.id) AS item_count,
               MAX(CASE WHEN ci.item_id = ? THEN 1 ELSE 0 END) AS has_item
        FROM collections c
        LEFT JOIN collection_items ci ON c.id = ci.collection_id
        WHERE c.user_id = ?
        GROUP BY c.id
        ORDER BY c.title ASC
        """,
        (item_id, g.user["id"]),
    ).fetchall()

    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "title": r["title"],
            "is_public": bool(r["is_public"]),
            "item_count": r["item_count"],
            "has_item": bool(r["has_item"]) if item_id else False,
        })
    return jsonify({"success": True, "collections": results})


@bp.route("/api/toggle-item", methods=["POST"])
@login_required
def api_toggle_item():
    """Toggle item presence in a collection (add if missing, remove if present)."""
    data = request.get_json() or {}
    item_id = data.get("item_id")
    collection_id = data.get("collection_id")

    if not item_id or not collection_id:
        return jsonify({"success": False, "error": "item_id and collection_id are required"}), 400

    db = get_db()
    collection = db.execute("SELECT * FROM collections WHERE id = ?", (collection_id,)).fetchone()
    if collection is None:
        return jsonify({"success": False, "error": "Collection not found"}), 404
    if collection["user_id"] != g.user["id"] and g.user["role"] != "admin":
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    existing = db.execute(
        "SELECT id FROM collection_items WHERE collection_id = ? AND item_id = ?",
        (collection_id, item_id),
    ).fetchone()

    if existing:
        db.execute(
            "DELETE FROM collection_items WHERE collection_id = ? AND item_id = ?",
            (collection_id, item_id),
        )
        in_collection = False
        msg = f"Removed from '{collection['title']}'"
    else:
        db.execute(
            "INSERT INTO collection_items (collection_id, item_id) VALUES (?, ?)",
            (collection_id, item_id),
        )
        in_collection = True
        msg = f"Added to '{collection['title']}'"

    db.execute("UPDATE collections SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (collection_id,))
    db.commit()

    return jsonify({
        "success": True,
        "in_collection": in_collection,
        "message": msg,
        "collection_title": collection["title"],
    })
