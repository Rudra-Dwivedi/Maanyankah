import json
import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g, abort, jsonify
from werkzeug.security import check_password_hash

from app.db import get_db
from app.auth_utils import admin_required
from app.services.sentiment import label
from app.services.item_media import with_image_urls, resolve_image_url
from app.services.image_fetcher import fetch_image_for_item, enrich_item_metadata

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@admin_required
def root():
    return redirect(url_for("admin.dashboard"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user is not None and g.user["role"] == "admin":
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        db = get_db()
        error = None

        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            error = "Incorrect username or password."
        elif not user["is_active"]:
            error = "This admin account has been deactivated."
        elif user["role"] != "admin":
            error = "This account isn't an admin account."

        if error is None:
            db.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],)
            )
            db.commit()
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("admin.dashboard"))

        flash(error)

    return render_template("admin_login.html")


@bp.route("/dashboard")
@admin_required
def dashboard():
    db = get_db()

    # Overview Metrics
    user_counts = db.execute(
        """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active,
            SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) as suspended,
            SUM(CASE WHEN role = 'admin' THEN 1 ELSE 0 END) as admins
        FROM users
        """
    ).fetchone()

    post_counts = db.execute(
        """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN sentiment_score > 0.15 THEN 1 ELSE 0 END) as positive,
            SUM(CASE WHEN sentiment_score < -0.15 THEN 1 ELSE 0 END) as negative,
            SUM(CASE WHEN sentiment_score BETWEEN -0.15 AND 0.15 THEN 1 ELSE 0 END) as neutral
        FROM posts
        """
    ).fetchone()

    pref_counts = db.execute(
        """
        SELECT 
            COUNT(*) as total,
            ROUND(AVG(rating), 2) as avg_rating
        FROM user_preferences
        """
    ).fetchone()

    item_counts = db.execute(
        """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN type = 'movie' THEN 1 ELSE 0 END) as movies,
            SUM(CASE WHEN type = 'song' THEN 1 ELSE 0 END) as songs,
            SUM(CASE WHEN type = 'team' THEN 1 ELSE 0 END) as teams
        FROM items
        """
    ).fetchone()

    group_count = db.execute("SELECT COUNT(*) as total FROM groups").fetchone()["total"]

    # Recent Activity Feed (combining registrations, posts, ratings)
    recent_signups = db.execute(
        """
        SELECT id, username, email, created_at, 'signup' as event_type
        FROM users
        ORDER BY created_at DESC
        LIMIT 8
        """
    ).fetchall()

    recent_posts = db.execute(
        """
        SELECT p.id, p.content, p.sentiment_score, p.created_at, 'post' as event_type,
               u.id as user_id, u.username, i.title as item_title
        FROM posts p
        JOIN users u ON p.user_id = u.id
        LEFT JOIN items i ON p.item_id = i.id
        ORDER BY p.created_at DESC
        LIMIT 8
        """
    ).fetchall()

    recent_ratings = db.execute(
        """
        SELECT r.id, r.rating, r.created_at, 'rating' as event_type,
               u.id as user_id, u.username, i.title as item_title, i.type as item_type
        FROM user_preferences r
        JOIN users u ON r.user_id = u.id
        JOIN items i ON r.item_id = i.id
        ORDER BY r.created_at DESC
        LIMIT 8
        """
    ).fetchall()

    # Merge and sort recent events
    events = []
    for s in recent_signups:
        events.append({
            "type": "signup",
            "time": s["created_at"],
            "user_id": s["id"],
            "username": s["username"],
            "detail": f"Registered new account ({s['email']})",
        })
    for p in recent_posts:
        events.append({
            "type": "post",
            "time": p["created_at"],
            "user_id": p["user_id"],
            "username": p["username"],
            "item_title": p["item_title"],
            "score": p["sentiment_score"],
            "sentiment": label(p["sentiment_score"]),
            "detail": p["content"] if len(p["content"]) <= 90 else p["content"][:87] + "...",
            "post_id": p["id"],
        })
    for r in recent_ratings:
        events.append({
            "type": "rating",
            "time": r["created_at"],
            "user_id": r["user_id"],
            "username": r["username"],
            "rating": r["rating"],
            "item_title": r["item_title"],
            "item_type": r["item_type"],
            "detail": f"Rated '{r['item_title']}' ({r['item_type']}) with {r['rating']} star{'s' if r['rating'] > 1 else ''}",
            "rating_id": r["id"],
        })

    events.sort(key=lambda e: e["time"] or "", reverse=True)
    events = events[:15]

    return render_template(
        "admin_dashboard.html",
        user_counts=user_counts,
        post_counts=post_counts,
        pref_counts=pref_counts,
        item_counts=item_counts,
        group_count=group_count,
        events=events,
        active_tab="dashboard",
    )


@bp.route("/users")
@admin_required
def users():
    db = get_db()
    query_param = request.args.get("q", "").strip()
    role_filter = request.args.get("role", "all")
    status_filter = request.args.get("status", "all")

    sql = """
        SELECT 
            u.id, u.username, u.email, u.role, u.is_active, u.created_at, u.avatar_url,
            COUNT(DISTINCT p.id) as post_count,
            COUNT(DISTINCT r.id) as rating_count
        FROM users u
        LEFT JOIN posts p ON p.user_id = u.id
        LEFT JOIN user_preferences r ON r.user_id = u.id
        WHERE 1=1
    """
    params = []

    if query_param:
        sql += " AND (u.username LIKE ? OR u.email LIKE ?)"
        pattern = f"%{query_param}%"
        params.extend([pattern, pattern])

    if role_filter in ("admin", "user"):
        sql += " AND u.role = ?"
        params.append(role_filter)

    if status_filter == "active":
        sql += " AND u.is_active = 1"
    elif status_filter == "suspended":
        sql += " AND u.is_active = 0"

    sql += " GROUP BY u.id ORDER BY u.created_at DESC"

    user_rows = db.execute(sql, params).fetchall()

    return render_template(
        "admin_users.html",
        users=user_rows,
        q=query_param,
        role=role_filter,
        status=status_filter,
        active_tab="users",
    )


@bp.route("/users/<int:user_id>")
@admin_required
def user_detail(user_id):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        abort(404)

    # User posts
    posts = db.execute(
        """
        SELECT p.*, i.title as item_title, i.type as item_type
        FROM posts p
        LEFT JOIN items i ON p.item_id = i.id
        WHERE p.user_id = ?
        ORDER BY p.created_at DESC
        """,
        (user_id,),
    ).fetchall()
    posts_with_labels = [
        {**dict(p), "sentiment_label": label(p["sentiment_score"])}
        for p in posts
    ]

    # User ratings
    ratings = db.execute(
        """
        SELECT r.*, i.title as item_title, i.type as item_type, i.genre_tags
        FROM user_preferences r
        JOIN items i ON r.item_id = i.id
        WHERE r.user_id = ?
        ORDER BY r.created_at DESC
        """,
        (user_id,),
    ).fetchall()

    # Social stats
    following = db.execute(
        """
        SELECT u.id, u.username
        FROM follows f
        JOIN users u ON f.followed_id = u.id
        WHERE f.follower_id = ?
        ORDER BY u.username
        """,
        (user_id,),
    ).fetchall()

    followers = db.execute(
        """
        SELECT u.id, u.username
        FROM follows f
        JOIN users u ON f.follower_id = u.id
        WHERE f.followed_id = ?
        ORDER BY u.username
        """,
        (user_id,),
    ).fetchall()

    # User groups
    groups = db.execute(
        """
        SELECT g.id, g.name, g.created_at,
               (CASE WHEN g.created_by = ? THEN 1 ELSE 0 END) as is_creator
        FROM groups g
        JOIN group_members gm ON g.id = gm.group_id
        WHERE gm.user_id = ?
        ORDER BY g.created_at DESC
        """,
        (user_id, user_id),
    ).fetchall()

    return render_template(
        "admin_user_detail.html",
        user=user,
        posts=posts_with_labels,
        ratings=ratings,
        following=following,
        followers=followers,
        groups=groups,
        active_tab="users",
    )


@bp.route("/users/<int:user_id>/toggle-status", methods=["POST"])
@admin_required
def toggle_user_status(user_id):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        flash("User not found.")
        return redirect(url_for("admin.users"))

    if user["id"] == g.user["id"]:
        flash("You cannot suspend your own admin account.")
        return redirect(request.referrer or url_for("admin.users"))

    new_status = 0 if user["is_active"] else 1
    db.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
    db.commit()

    action_text = "suspended" if new_status == 0 else "reactivated"
    flash(f"User '{user['username']}' has been {action_text}.")
    return redirect(request.referrer or url_for("admin.users"))


@bp.route("/users/<int:user_id>/toggle-role", methods=["POST"])
@admin_required
def toggle_user_role(user_id):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        flash("User not found.")
        return redirect(url_for("admin.users"))

    if user["id"] == g.user["id"]:
        flash("You cannot change your own admin role.")
        return redirect(request.referrer or url_for("admin.users"))

    if user["role"] == "admin":
        # Check if there are other active admins
        other_admins = db.execute(
            "SELECT COUNT(*) as count FROM users WHERE role = 'admin' AND is_active = 1 AND id != ?",
            (user_id,),
        ).fetchone()["count"]
        if other_admins == 0:
            flash("Cannot demote the only remaining active admin.")
            return redirect(request.referrer or url_for("admin.users"))
        new_role = "user"
    else:
        new_role = "admin"

    db.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
    db.commit()

    flash(f"User '{user['username']}' role changed to {new_role}.")
    return redirect(request.referrer or url_for("admin.users"))


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        flash("User not found.")
        return redirect(url_for("admin.users"))

    if user["id"] == g.user["id"]:
        flash("You cannot delete your own account.")
        return redirect(url_for("admin.users"))

    if user["role"] == "admin":
        other_admins = db.execute(
            "SELECT COUNT(*) as count FROM users WHERE role = 'admin' AND id != ?",
            (user_id,),
        ).fetchone()["count"]
        if other_admins == 0:
            flash("Cannot delete the only remaining admin.")
            return redirect(url_for("admin.users"))

    # Cascading deletions inside transaction
    db.execute("DELETE FROM user_preferences WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM posts WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM follows WHERE follower_id = ? OR followed_id = ?", (user_id, user_id))
    db.execute("DELETE FROM group_members WHERE user_id = ?", (user_id,))
    # Delete groups created by this user and their memberships
    created_groups = db.execute("SELECT id FROM groups WHERE created_by = ?", (user_id,)).fetchall()
    for grp in created_groups:
        db.execute("DELETE FROM group_members WHERE group_id = ?", (grp["id"],))
        db.execute("DELETE FROM groups WHERE id = ?", (grp["id"],))
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()

    flash(f"User '{user['username']}' and all their associated data have been deleted.")
    return redirect(url_for("admin.users"))


@bp.route("/posts")
@admin_required
def posts():
    db = get_db()
    q = request.args.get("q", "").strip()
    sentiment_filter = request.args.get("sentiment", "all")

    sql = """
        SELECT p.*, u.username, u.avatar_url, u.is_active as user_active, i.title as item_title, i.type as item_type
        FROM posts p
        JOIN users u ON p.user_id = u.id
        LEFT JOIN items i ON p.item_id = i.id
        WHERE 1=1
    """
    params = []

    if q:
        sql += " AND (p.content LIKE ? OR u.username LIKE ? OR i.title LIKE ?)"
        pat = f"%{q}%"
        params.extend([pat, pat, pat])

    if sentiment_filter == "positive":
        sql += " AND p.sentiment_score > 0.15"
    elif sentiment_filter == "negative":
        sql += " AND p.sentiment_score < -0.15"
    elif sentiment_filter == "neutral":
        sql += " AND p.sentiment_score BETWEEN -0.15 AND 0.15"

    sql += " ORDER BY p.created_at DESC"

    rows = db.execute(sql, params).fetchall()
    posts_list = [
        {**dict(r), "sentiment_label": label(r["sentiment_score"])}
        for r in rows
    ]

    return render_template(
        "admin_posts.html",
        posts=posts_list,
        q=q,
        sentiment=sentiment_filter,
        active_tab="posts",
    )


@bp.route("/posts/<int:post_id>/delete", methods=["POST"])
@admin_required
def delete_post(post_id):
    db = get_db()
    db.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    db.commit()
    flash("Post removed by administrator.")
    return redirect(request.referrer or url_for("admin.posts"))


@bp.route("/ratings")
@admin_required
def ratings():
    db = get_db()
    q = request.args.get("q", "").strip()
    type_filter = request.args.get("type", "all")
    stars_filter = request.args.get("stars", "all")

    sql = """
        SELECT r.*, u.username, u.avatar_url, u.is_active as user_active,
               i.title as item_title, i.type as item_type, i.genre_tags
        FROM user_preferences r
        JOIN users u ON r.user_id = u.id
        JOIN items i ON r.item_id = i.id
        WHERE 1=1
    """
    params = []

    if q:
        sql += " AND (u.username LIKE ? OR i.title LIKE ?)"
        pat = f"%{q}%"
        params.extend([pat, pat])

    if type_filter in ("movie", "song", "team"):
        sql += " AND i.type = ?"
        params.append(type_filter)

    if stars_filter in ("1", "2", "3", "4", "5"):
        sql += " AND r.rating = ?"
        params.append(int(stars_filter))

    sql += " ORDER BY r.created_at DESC"

    ratings_list = db.execute(sql, params).fetchall()

    return render_template(
        "admin_ratings.html",
        ratings=ratings_list,
        q=q,
        item_type=type_filter,
        stars=stars_filter,
        active_tab="ratings",
    )


@bp.route("/posts/<int:post_id>/toggle-pin", methods=["POST"])
@admin_required
def toggle_pin_post(post_id):
    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if post is None:
        flash("Post not found.")
        return redirect(url_for("admin.posts"))

    new_pinned = 0 if post["is_pinned"] else 1
    db.execute("UPDATE posts SET is_pinned = ? WHERE id = ?", (new_pinned, post_id))
    db.commit()
    status_msg = "pinned as an official announcement" if new_pinned else "unpinned"
    flash(f"Post #{post_id} has been {status_msg}.")
    return redirect(request.referrer or url_for("admin.posts"))


@bp.route("/ratings/<int:rating_id>/delete", methods=["POST"])
@admin_required
def delete_rating(rating_id):
    db = get_db()
    db.execute("DELETE FROM user_preferences WHERE id = ?", (rating_id,))
    db.commit()
    flash("Rating removed by administrator.")
    return redirect(request.referrer or url_for("admin.ratings"))


@bp.route("/items")
@admin_required
def items():
    db = get_db()
    q = request.args.get("q", "").strip()
    item_type = request.args.get("type", "all")

    sql = """
        SELECT i.*, COUNT(r.id) as rating_count, ROUND(AVG(r.rating), 1) as avg_rating
        FROM items i
        LEFT JOIN user_preferences r ON i.id = r.item_id
        WHERE 1=1
    """
    params = []

    if q:
        sql += " AND (i.title LIKE ? OR i.genre_tags LIKE ?)"
        pat = f"%{q}%"
        params.extend([pat, pat])

    if item_type in ("movie", "song", "team"):
        sql += " AND i.type = ?"
        params.append(item_type)

    sql += " GROUP BY i.id ORDER BY i.created_at DESC"

    rows = db.execute(sql, params).fetchall()
    items_list = with_image_urls(rows)

    return render_template(
        "admin_items.html",
        items=items_list,
        q=q,
        item_type=item_type,
        active_tab="items",
    )


@bp.route("/items/check-duplicate")
@admin_required
def check_duplicate():
    item_type = request.args.get("type", "").strip()
    title = request.args.get("title", "").strip()

    if not title or not item_type:
        return jsonify({"exists": False})

    db = get_db()
    row = db.execute(
        """
        SELECT i.id, i.title, i.type, ROUND(AVG(r.rating), 1) as avg_rating
        FROM items i
        LEFT JOIN user_preferences r ON i.id = r.item_id
        WHERE i.type = ? AND LOWER(TRIM(i.title)) = LOWER(TRIM(?))
        GROUP BY i.id
        """,
        (item_type, title),
    ).fetchone()

    if row:
        return jsonify({
            "exists": True,
            "id": row["id"],
            "title": row["title"],
            "avg_rating": row["avg_rating"] or 0,
        })
    return jsonify({"exists": False})


@bp.route("/items/create", methods=["POST"])
@admin_required
def create_item():
    item_type = request.form.get("type", "").strip()
    title = request.form.get("title", "").strip()
    genre_tags = request.form.get("genre_tags", "").strip()
    image_url = request.form.get("image_url", "").strip()

    if not title or item_type not in ("movie", "song", "team"):
        flash("Title and a valid item type (movie, song, team) are required.")
        return redirect(url_for("admin.items"))

    db = get_db()

    # Proactive normalized duplicate check
    existing = db.execute(
        "SELECT id, title FROM items WHERE type = ? AND LOWER(TRIM(title)) = LOWER(TRIM(?))",
        (item_type, title),
    ).fetchone()

    if existing:
        flash(f"A {item_type} titled '{existing['title']}' already exists in the catalog (ID #{existing['id']}). Duplicate prevented.")
        return redirect(url_for("admin.items"))

    auto_fetched = False
    if not image_url:
        found_url = fetch_image_for_item(item_type, title)
        if found_url:
            image_url = found_url
            auto_fetched = True

    metadata = {}
    if image_url:
        metadata["image_url"] = image_url

    try:
        db.execute(
            "INSERT INTO items (type, title, genre_tags, metadata) VALUES (?, ?, ?, ?)",
            (item_type, title, genre_tags, json.dumps(metadata)),
        )
        db.commit()
    except sqlite3.IntegrityError:
        flash(f"Database constraint prevented inserting '{title}' as a duplicate {item_type}.")
        return redirect(url_for("admin.items"))

    if auto_fetched:
        flash(f"Added '{title}' ({item_type}) with automatically resolved image!")
    else:
        flash(f"Successfully added '{title}' ({item_type}) to the catalog.")
    return redirect(url_for("admin.items"))


@bp.route("/items/deduplicate", methods=["POST"])
@admin_required
def deduplicate_catalog():
    db = get_db()
    # Find all clusters with duplicates (same type and lower(trim(title)))
    dup_clusters = db.execute(
        """
        SELECT type, LOWER(TRIM(title)) as norm_title, COUNT(*) as cnt
        FROM items
        GROUP BY type, LOWER(TRIM(title))
        HAVING COUNT(*) > 1
        """
    ).fetchall()

    if not dup_clusters:
        flash("Catalog is already clean! No duplicate items found.")
        return redirect(url_for("admin.items"))

    merged_clusters_count = len(dup_clusters)
    removed_duplicates_count = 0

    for cluster in dup_clusters:
        items_in_cluster = db.execute(
            """
            SELECT id, metadata, external_id
            FROM items
            WHERE type = ? AND LOWER(TRIM(title)) = ?
            ORDER BY id ASC
            """,
            (cluster["type"], cluster["norm_title"]),
        ).fetchall()

        canonical_id = items_in_cluster[0]["id"]
        duplicate_ids = [row["id"] for row in items_in_cluster[1:]]

        for dup_id in duplicate_ids:
            # 1. Consolidate user_preferences
            # Delete conflicting ratings on duplicate if user already rated canonical
            db.execute(
                """
                DELETE FROM user_preferences
                WHERE item_id = ? AND user_id IN (
                    SELECT user_id FROM user_preferences WHERE item_id = ?
                )
                """,
                (dup_id, canonical_id),
            )
            # Reassign non-conflicting ratings
            db.execute("UPDATE user_preferences SET item_id = ? WHERE item_id = ?", (canonical_id, dup_id))

            # 2. Consolidate collection_items
            db.execute(
                """
                DELETE FROM collection_items
                WHERE item_id = ? AND collection_id IN (
                    SELECT collection_id FROM collection_items WHERE item_id = ?
                )
                """,
                (dup_id, canonical_id),
            )
            db.execute("UPDATE collection_items SET item_id = ? WHERE item_id = ?", (canonical_id, dup_id))

            # 3. Consolidate posts
            db.execute("UPDATE posts SET item_id = ? WHERE item_id = ?", (canonical_id, dup_id))

            # 4. Remove duplicate item
            db.execute("DELETE FROM items WHERE id = ?", (dup_id,))
            removed_duplicates_count += 1

    db.commit()
    flash(f"Successfully cleaned catalog! Consolidated {removed_duplicates_count} duplicate item(s) across {merged_clusters_count} cluster(s).")
    return redirect(url_for("admin.items"))


@bp.route("/items/auto-fetch-images", methods=["POST"])
@admin_required
def auto_fetch_images():
    db = get_db()
    items = db.execute("SELECT id, type, title, metadata FROM items").fetchall()
    updated_count = 0
    force = request.form.get("force") == "1" or request.args.get("force") == "1"

    for item in items:
        current_img = resolve_image_url(item)
        if not current_img or force:
            found_img = fetch_image_for_item(item["type"], item["title"])
            if found_img:
                new_meta = enrich_item_metadata(item["metadata"], found_img)
                db.execute("UPDATE items SET metadata = ? WHERE id = ?", (new_meta, item["id"]))
                updated_count += 1

    if updated_count > 0:
        db.commit()
        if force:
            flash(f"Successfully upgraded {updated_count} catalog item(s) to high-definition artwork!")
        else:
            flash(f"Successfully auto-fetched and saved images for {updated_count} catalog item(s)!")
    else:
        flash("All catalog items already have images or no additional artwork was found.")

    return redirect(url_for("admin.items"))


@bp.route("/items/<int:item_id>/delete", methods=["POST"])
@admin_required
def delete_item(item_id):
    db = get_db()
    item = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if item is None:
        flash("Item not found.")
        return redirect(url_for("admin.items"))

    # Cascading removal in transaction
    db.execute("DELETE FROM user_preferences WHERE item_id = ?", (item_id,))
    db.execute("UPDATE posts SET item_id = NULL WHERE item_id = ?", (item_id,))
    db.execute("DELETE FROM items WHERE id = ?", (item_id,))
    db.commit()

    flash(f"Item '{item['title']}' and its rating associations were removed.")
    return redirect(url_for("admin.items"))
