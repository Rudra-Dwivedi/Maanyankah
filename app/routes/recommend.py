from flask import Blueprint, render_template, request, g, redirect, url_for, flash, abort

from app.db import get_db
from app.auth_utils import login_required
from app.services.recommender import similar_users, group_recommendation
from app.services.item_media import resolve_image_url, with_image_urls
from app.services.sentiment import label

bp = Blueprint("recommend", __name__, url_prefix="/recommend")


@bp.route("/people")
@login_required
def people():
    """Show users with the most similar taste, and all community members so users can discover and follow each other."""
    db = get_db()
    q = request.args.get("q", "").strip()

    following_ids = {
        row["followed_id"]
        for row in db.execute(
            "SELECT followed_id FROM follows WHERE follower_id = ?", (g.user["id"],)
        ).fetchall()
    }

    # 1. Collaborative filtering: top taste matches
    matches = similar_users(g.user["id"], top_n=10)
    results = []
    matched_uids = set()
    for uid, score in matches:
        matched_uids.add(uid)
        user = db.execute(
            "SELECT id, username, avatar_url, role FROM users WHERE id = ? AND is_active = 1", (uid,)
        ).fetchone()
        if user:
            results.append(
                {
                    "user": user,
                    "score": round(float(score), 3),
                    "following": user["id"] in following_ids,
                }
            )

    # 2. All active community members so anyone can be discovered and followed
    if q:
        members_query = """
            SELECT u.id, u.username, u.avatar_url, u.bio, u.role, u.last_login, u.created_at,
                   (SELECT COUNT(*) FROM user_preferences WHERE user_id = u.id) AS rating_count,
                   (SELECT COUNT(*) FROM follows WHERE followed_id = u.id) AS follower_count
            FROM users u
            WHERE u.id != ? AND u.is_active = 1 AND u.username LIKE ?
            ORDER BY rating_count DESC, u.created_at DESC
        """
        all_members_rows = db.execute(members_query, (g.user["id"], f"%{q}%")).fetchall()
    else:
        members_query = """
            SELECT u.id, u.username, u.avatar_url, u.bio, u.role, u.last_login, u.created_at,
                   (SELECT COUNT(*) FROM user_preferences WHERE user_id = u.id) AS rating_count,
                   (SELECT COUNT(*) FROM follows WHERE followed_id = u.id) AS follower_count
            FROM users u
            WHERE u.id != ? AND u.is_active = 1
            ORDER BY rating_count DESC, u.created_at DESC
        """
        all_members_rows = db.execute(members_query, (g.user["id"],)).fetchall()

    members = []
    for m in all_members_rows:
        members.append({
            "user": m,
            "following": m["id"] in following_ids,
            "is_matched": m["id"] in matched_uids,
        })

    return render_template(
        "similar_people.html",
        matches=results,
        members=members,
        search_query=q,
    )


@bp.route("/follow/<int:user_id>", methods=["POST"])
@login_required
def follow(user_id):
    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO follows (follower_id, followed_id) VALUES (?, ?)",
        (g.user["id"], user_id),
    )
    db.commit()
    return redirect(request.referrer or url_for("recommend.people"))


@bp.route("/unfollow/<int:user_id>", methods=["POST"])
@login_required
def unfollow(user_id):
    db = get_db()
    db.execute(
        "DELETE FROM follows WHERE follower_id = ? AND followed_id = ?",
        (g.user["id"], user_id),
    )
    db.commit()
    return redirect(request.referrer or url_for("recommend.people"))


@bp.route("/user/<username>")
def profile(username):
    """Public user profile showing someone's taste, ratings, and feed activity."""
    db = get_db()
    user = db.execute(
        "SELECT id, username, role, is_active, created_at, avatar_url, bio FROM users WHERE username = ?",
        (username,),
    ).fetchone()

    if user is None:
        abort(404)

    if not user["is_active"] and (g.user is None or g.user["role"] != "admin"):
        abort(404)

    # User ratings with media
    ratings = db.execute(
        """
        SELECT r.rating, r.created_at, i.id as item_id, i.title, i.type, i.genre_tags, i.metadata
        FROM user_preferences r
        JOIN items i ON r.item_id = i.id
        WHERE r.user_id = ?
        ORDER BY r.rating DESC, r.created_at DESC
        """,
        (user["id"],),
    ).fetchall()
    ratings_with_media = with_image_urls(ratings)

    # User posts
    posts = db.execute(
        """
        SELECT p.*, i.title as item_title, i.type as item_type
        FROM posts p
        LEFT JOIN items i ON p.item_id = i.id
        WHERE p.user_id = ?
        ORDER BY p.is_pinned DESC, p.created_at DESC
        LIMIT 20
        """,
        (user["id"],),
    ).fetchall()
    posts_with_labels = [
        {**dict(p), "sentiment_label": label(p["sentiment_score"])}
        for p in posts
    ]

    # Follow counts & state
    followers_count = db.execute(
        "SELECT COUNT(*) as c FROM follows WHERE followed_id = ?", (user["id"],)
    ).fetchone()["c"]

    following_count = db.execute(
        "SELECT COUNT(*) as c FROM follows WHERE follower_id = ?", (user["id"],)
    ).fetchone()["c"]

    is_following = False
    if g.user is not None and g.user["id"] != user["id"]:
        f = db.execute(
            "SELECT 1 FROM follows WHERE follower_id = ? AND followed_id = ?",
            (g.user["id"], user["id"]),
        ).fetchone()
        is_following = f is not None

    # User collections
    is_profile_owner = g.user is not None and (g.user["id"] == user["id"] or g.user["role"] == "admin")
    if is_profile_owner:
        user_collections = db.execute(
            """
            SELECT c.*,
                   COUNT(ci.id) AS item_count,
                   SUM(CASE WHEN i.type = 'movie' THEN 1 ELSE 0 END) AS movie_count,
                   SUM(CASE WHEN i.type = 'song' THEN 1 ELSE 0 END) AS song_count
            FROM collections c
            LEFT JOIN collection_items ci ON c.id = ci.collection_id
            LEFT JOIN items i ON ci.item_id = i.id
            WHERE c.user_id = ?
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            """,
            (user["id"],),
        ).fetchall()
    else:
        user_collections = db.execute(
            """
            SELECT c.*,
                   COUNT(ci.id) AS item_count,
                   SUM(CASE WHEN i.type = 'movie' THEN 1 ELSE 0 END) AS movie_count,
                   SUM(CASE WHEN i.type = 'song' THEN 1 ELSE 0 END) AS song_count
            FROM collections c
            LEFT JOIN collection_items ci ON c.id = ci.collection_id
            LEFT JOIN items i ON ci.item_id = i.id
            WHERE c.user_id = ? AND c.is_public = 1
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            """,
            (user["id"],),
        ).fetchall()

    return render_template(
        "user_profile.html",
        profile_user=user,
        ratings=ratings_with_media,
        posts=posts_with_labels,
        followers_count=followers_count,
        following_count=following_count,
        is_following=is_following,
        collections=user_collections,
    )


@bp.route("/group", methods=["GET", "POST"])
@login_required
def group():
    """Pick a group of users and get a ranked group recommendation."""
    db = get_db()
    # Only show members the logged-in user is following (excluding admins and suspended accounts)
    all_users = db.execute(
        """
        SELECT u.id, u.username, u.avatar_url
        FROM follows f
        JOIN users u ON f.followed_id = u.id
        WHERE f.follower_id = ? AND u.role != 'admin' AND u.is_active = 1
        ORDER BY u.username
        """,
        (g.user["id"],),
    ).fetchall()

    winner = None
    runner_ups = []
    winner_members = []
    explanation = None
    selected_ids = []
    strategy = "average"
    item_type = None

    if request.method == "POST":
        valid_uids = {row["id"] for row in all_users}
        selected_ids = [int(uid) for uid in request.form.getlist("user_ids") if int(uid) in valid_uids]
        strategy = request.form.get("strategy", "average")
        item_type = request.form.get("item_type") or None

        if g.user["id"] not in selected_ids:
            selected_ids.append(g.user["id"])

        if len(selected_ids) < 2:
            flash("Pick at least one other person to form a group.")
        else:
            recommendations = group_recommendation(
                selected_ids, item_type=item_type, strategy=strategy, top_n=10
            )
            for rec in recommendations:
                item_row = db.execute(
                    "SELECT * FROM items WHERE id = ?", (rec["item_id"],)
                ).fetchone()
                rec["image_url"] = resolve_image_url(item_row) if item_row else None

            if recommendations:
                winner = recommendations[0]
                runner_ups = recommendations[1:]

                member_rows = [
                    db.execute(
                        "SELECT id, username, avatar_url FROM users WHERE id = ?", (uid,)
                    ).fetchone()
                    for uid in selected_ids
                ]
                winner_members = list(zip(member_rows, winner["individual_scores"]))

                if strategy == "least_misery":
                    lowest = min(winner["individual_scores"])
                    explanation = (
                        f"Nobody in the group is predicted to rate this below "
                        f"{lowest} / 5 — the safest pick for a picky group."
                    )
                else:
                    explanation = (
                        f"Averaged across the group, this scores {winner['score']} / 5 "
                        f"— the highest combined score of anything considered."
                    )

    return render_template(
        "group_recommend.html",
        all_users=all_users,
        winner=winner,
        winner_members=winner_members,
        explanation=explanation,
        runner_ups=runner_ups,
        selected_ids=selected_ids,
        strategy=strategy,
        item_type=item_type,
    )
