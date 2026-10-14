from flask import Blueprint, render_template, request, redirect, url_for, g, flash, jsonify

from app.db import get_db
from app.auth_utils import login_required
from app.services.sentiment import analyze, label
from app.services.item_media import resolve_image_url
from app.services.gamification import get_user_badges

bp = Blueprint("feed", __name__, url_prefix="/feed")


@bp.route("/", methods=["GET", "POST"])
def feed():
    db = get_db()

    if request.method == "POST":
        if g.user is None:
            flash("Log in to post.")
            return redirect(url_for("auth.login"))

        content = request.form["content"].strip()
        item_id = request.form.get("item_id") or None
        is_pinned = 1 if (g.user["role"] == "admin" and request.form.get("is_pinned")) else 0
        is_spoiler = 1 if request.form.get("is_spoiler") in ("1", "true", "on", True) else 0
        spoiler_warning = request.form.get("spoiler_warning", "").strip()
        if not content:
            flash("Post can't be empty.")
        else:
            score = analyze(content)
            db.execute(
                "INSERT INTO posts (user_id, item_id, content, sentiment_score, is_pinned, is_spoiler, spoiler_warning) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (g.user["id"], item_id, content, score, is_pinned, is_spoiler, spoiler_warning),
            )
            db.commit()
            if is_pinned:
                flash("Official announcement published and pinned to feed!")
            elif is_spoiler:
                flash("Spoiler-shielded post published safely!")
        return redirect(url_for("feed.feed"))

    filter_tab = request.args.get("filter", "all")

    # Base query
    query = """
        SELECT posts.*, 
               users.username, users.role AS user_role, users.avatar_url, 
               items.title AS item_title, items.type AS item_type, items.metadata AS item_metadata,
               COALESCE(ROUND((SELECT AVG(rating) FROM user_preferences WHERE item_id = items.id), 1), 0) AS item_avg_rating
        FROM posts
        JOIN users ON posts.user_id = users.id
        LEFT JOIN items ON posts.item_id = items.id
    """
    params = []

    if filter_tab == "pinned":
        query += " WHERE posts.is_pinned = 1"
    elif filter_tab == "positive":
        query += " WHERE posts.sentiment_score > 0.15"
    elif filter_tab in ("movie", "song", "team"):
        query += " WHERE items.type = ?"
        params.append(filter_tab)

    query += " ORDER BY posts.is_pinned DESC, posts.created_at DESC LIMIT 50"
    posts = db.execute(query, params).fetchall()

    # Pre-fetch reactions for these posts
    post_ids = [p["id"] for p in posts]
    reactions_by_post = {pid: {"fire": 0, "love": 0, "insightful": 0, "mindblown": 0, "disagree": 0} for pid in post_ids}
    user_reactions_map = {}

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
            if pid in reactions_by_post and rxn in reactions_by_post[pid]:
                reactions_by_post[pid][rxn] = rc["c"]

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
                user_reactions_map[ur["post_id"]] = ur["reaction"]

    # Cache user badges to avoid redundant calculations
    user_badge_cache = {}

    posts_with_labels = []
    for post in posts:
        post_dict = dict(post)
        post_dict["sentiment_label"] = label(post["sentiment_score"])
        
        # Author trust badges
        uid = post["user_id"]
        if uid not in user_badge_cache:
            user_badge_cache[uid] = get_user_badges(db, uid)
        post_dict["author_badges"] = user_badge_cache[uid]

        # Post reactions
        post_dict["reactions"] = reactions_by_post.get(post["id"], {"fire": 0, "love": 0, "insightful": 0, "mindblown": 0, "disagree": 0})
        post_dict["total_reactions"] = sum(post_dict["reactions"].values())
        post_dict["user_reaction"] = user_reactions_map.get(post["id"])

        # Resolve tagged item image if present
        if post["item_title"]:
            item_mock = {
                "type": post["item_type"],
                "title": post["item_title"],
                "metadata": post["item_metadata"]
            }
            post_dict["item_image_url"] = resolve_image_url(item_mock)
        else:
            post_dict["item_image_url"] = None
        posts_with_labels.append(post_dict)

    # Compute Community Mood Pulse from all recent posts
    sentiment_rows = db.execute("SELECT sentiment_score FROM posts ORDER BY id DESC LIMIT 100").fetchall()
    total_posts = len(sentiment_rows)
    pos_count = sum(1 for r in sentiment_rows if r["sentiment_score"] > 0.15)
    neu_count = sum(1 for r in sentiment_rows if -0.15 <= r["sentiment_score"] <= 0.15)
    crit_count = sum(1 for r in sentiment_rows if r["sentiment_score"] < -0.15)

    if total_posts > 0:
        pos_pct = round((pos_count / total_posts) * 100)
        neu_pct = round((neu_count / total_posts) * 100)
        crit_pct = max(0, 100 - pos_pct - neu_pct)
    else:
        pos_pct, neu_pct, crit_pct = 70, 20, 10

    if pos_pct >= 60:
        mood_vibe = "✨ Highly Positive & Inspiring"
    elif crit_pct >= 35:
        mood_vibe = "⚡ Passionate Critiques & Lively Debate"
    elif pos_pct >= 40:
        mood_vibe = "🌸 Mindful & Upbeat Community Vibe"
    else:
        mood_vibe = "⚖️ Thoughtful & Balanced Perspectives"

    mood_summary = {
        "pos_pct": pos_pct,
        "neu_pct": neu_pct,
        "crit_pct": crit_pct,
        "vibe": mood_vibe,
        "total_analyzed": total_posts,
    }

    # Popular / Trending tagged items in feed
    trending_items = db.execute(
        """
        SELECT i.id, i.title, i.type, i.metadata, COUNT(p.id) AS post_count
        FROM items i
        JOIN posts p ON i.id = p.item_id
        GROUP BY i.id
        ORDER BY post_count DESC
        LIMIT 5
        """
    ).fetchall()

    all_items = db.execute("SELECT id, title, type FROM items ORDER BY type, title").fetchall()

    return render_template(
        "feed.html",
        posts=posts_with_labels,
        items=all_items,
        active_filter=filter_tab,
        trending_items=trending_items,
        mood_summary=mood_summary,
    )


@bp.route("/<int:post_id>/react", methods=["POST"])
def react(post_id):
    """AJAX endpoint for toggling quick emoji reactions (fire, love, insightful, mindblown, disagree)."""
    if g.user is None:
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": False, "error": "Login required"}), 401
        flash("Please log in to react to posts.")
        return redirect(url_for("auth.login"))

    db = get_db()
    data = request.get_json(silent=True) or request.form
    reaction = data.get("reaction", "").strip().lower()

    valid_reactions = {"fire", "love", "insightful", "mindblown", "disagree"}
    if reaction not in valid_reactions:
        return jsonify({"success": False, "error": "Invalid reaction type"}), 400

    # Check existing user reaction
    existing = db.execute(
        "SELECT reaction FROM post_reactions WHERE user_id = ? AND post_id = ?",
        (g.user["id"], post_id),
    ).fetchone()

    new_user_reaction = None
    if existing and existing["reaction"] == reaction:
        # Toggle off if tapped identical emoji
        db.execute(
            "DELETE FROM post_reactions WHERE user_id = ? AND post_id = ?",
            (g.user["id"], post_id),
        )
    else:
        # Update or insert
        db.execute(
            """
            INSERT INTO post_reactions (user_id, post_id, reaction)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, post_id) DO UPDATE SET reaction = excluded.reaction
            """,
            (g.user["id"], post_id, reaction),
        )
        new_user_reaction = reaction
    db.commit()

    # Recompute live tallies
    counts = {r: 0 for r in valid_reactions}
    rows = db.execute(
        "SELECT reaction, COUNT(*) as c FROM post_reactions WHERE post_id = ? GROUP BY reaction",
        (post_id,),
    ).fetchall()
    for r in rows:
        if r["reaction"] in counts:
            counts[r["reaction"]] = r["c"]

    total = sum(counts.values())

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "success": True,
            "post_id": post_id,
            "reactions": counts,
            "user_reaction": new_user_reaction,
            "total": total,
        })
    return redirect(request.referrer or url_for("feed.feed"))
