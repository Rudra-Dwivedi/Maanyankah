import os
import uuid
from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.utils import secure_filename

from app.auth_utils import login_required
from app.db import get_db
from app.services.video_helper import parse_video_source

bp = Blueprint("shorts", __name__, url_prefix="/shorts")

ALLOWED_VIDEO_EXTENSIONS = {"mp4", "webm", "ogg", "mov"}
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

REACTION_TYPES = [
    ("fire", "🔥", "Fire"),
    ("love", "❤️", "Loved It"),
    ("mindblown", "🤯", "Mind-Blowing"),
    ("applause", "👏", "Brilliant"),
    ("cinema", "🎬", "Pure Cinema"),
    ("masterpiece", "🏆", "Masterpiece"),
]


def allowed_video(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS


def allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


@bp.route("/")
@bp.route("")
def index():
    """Browse community short films and indie cinema."""
    db = get_db()
    active_genre = request.args.get("genre", "").strip()
    active_sort = request.args.get("sort", "newest").strip()
    search_q = request.args.get("q", "").strip()

    sql = """
        SELECT s.*, u.username as creator_username, u.avatar_url as creator_avatar,
               (SELECT COUNT(*) FROM short_film_reactions r WHERE r.short_id = s.id) as total_reactions,
               (SELECT COUNT(*) FROM short_film_comments c WHERE c.short_id = s.id) as total_comments
        FROM short_films s
        JOIN users u ON s.user_id = u.id
        WHERE 1=1
    """
    params = []

    if active_genre:
        sql += " AND s.genre_tags LIKE ?"
        params.append(f"%{active_genre}%")

    if search_q:
        sql += " AND (s.title LIKE ? OR s.description LIKE ? OR s.director_name LIKE ?)"
        wild = f"%{search_q}%"
        params.extend([wild, wild, wild])

    if active_sort == "popular":
        sql += " ORDER BY total_reactions DESC, s.views_count DESC"
    elif active_sort == "discussed":
        sql += " ORDER BY total_comments DESC, s.created_at DESC"
    elif active_sort == "views":
        sql += " ORDER BY s.views_count DESC"
    else:
        sql += " ORDER BY s.created_at DESC"

    cursor = db.execute(sql, params)
    shorts = cursor.fetchall()

    # Pre-parse video sources for thumbnails / badge info
    enhanced_shorts = []
    for row in shorts:
        item = dict(row)
        video_info = parse_video_source(item["video_url"])
        if not item.get("thumbnail_url"):
            item["thumbnail_url"] = video_info.get("thumbnail_url")
        item["video_info"] = video_info
        enhanced_shorts.append(item)

    # Spotlight top film
    spotlight_film = enhanced_shorts[0] if enhanced_shorts else None

    # Genre tags catalog for filtering
    genres_list = ["Sci-Fi", "Drama", "Animation", "Musical", "Thriller", "Sports", "Documentary", "Comedy"]

    return render_template(
        "shorts/index.html",
        shorts=enhanced_shorts,
        spotlight=spotlight_film,
        active_genre=active_genre,
        active_sort=active_sort,
        search_q=search_q,
        genres_list=genres_list,
    )


@bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    """Submit / upload a short film with either local video upload or online video URL."""
    db = get_db()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        director_name = request.form.get("director_name", "").strip() or g.user["username"]
        duration = request.form.get("duration", "").strip() or "5 min"
        genre_tags = request.form.get("genre_tags", "").strip() or "Indie"
        video_url = request.form.get("video_url", "").strip()
        thumbnail_url = request.form.get("thumbnail_url", "").strip()

        if not title:
            flash("Please enter a title for your film.")
            return redirect(url_for("shorts.upload"))

        final_video_url = None
        video_type = "youtube"

        # 1. Check direct video file upload
        file = request.files.get("video_file")
        if file and file.filename != "":
            if not allowed_video(file.filename):
                flash("Invalid video format. Allowed formats: MP4, WEBM, MOV, OGG.")
                return redirect(url_for("shorts.upload"))

            ext = file.filename.rsplit(".", 1)[1].lower()
            safe_name = f"short_{g.user['id']}_{uuid.uuid4().hex[:10]}.{ext}"
            upload_dir = os.path.join(current_app.root_path, "static", "uploads", "shorts_videos")
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, safe_name)
            file.save(file_path)

            final_video_url = url_for("static", filename=f"uploads/shorts_videos/{safe_name}")
            video_type = "html5"
        elif video_url:
            parsed = parse_video_source(video_url)
            final_video_url = parsed["raw_url"]
            video_type = parsed["video_type"]
            if not thumbnail_url and parsed.get("thumbnail_url"):
                thumbnail_url = parsed["thumbnail_url"]
        else:
            flash("Please either upload a video file or provide a video link (YouTube, Vimeo, MP4).")
            return redirect(url_for("shorts.upload"))

        # 2. Check custom thumbnail image file upload
        thumb_file = request.files.get("thumbnail_file")
        if thumb_file and thumb_file.filename != "":
            if allowed_image(thumb_file.filename):
                ext = thumb_file.filename.rsplit(".", 1)[1].lower()
                thumb_name = f"thumb_{g.user['id']}_{uuid.uuid4().hex[:10]}.{ext}"
                upload_dir = os.path.join(current_app.root_path, "static", "uploads", "shorts_videos")
                os.makedirs(upload_dir, exist_ok=True)
                thumb_file.save(os.path.join(upload_dir, thumb_name))
                thumbnail_url = url_for("static", filename=f"uploads/shorts_videos/{thumb_name}")

        cursor = db.execute(
            """INSERT INTO short_films 
               (user_id, title, description, director_name, duration, genre_tags, video_url, video_type, thumbnail_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                g.user["id"],
                title,
                description,
                director_name,
                duration,
                genre_tags,
                final_video_url,
                video_type,
                thumbnail_url or None,
            ),
        )
        db.commit()
        new_id = cursor.lastrowid
        flash("🎬 Your short film has been premiered successfully to the community!")
        return redirect(url_for("shorts.detail", short_id=new_id))

    return render_template("shorts/upload.html")


@bp.route("/<int:short_id>")
def detail(short_id):
    """Watch page for a community short film with player, reactions, and discussion thread."""
    db = get_db()

    # Increment view count
    db.execute("UPDATE short_films SET views_count = views_count + 1 WHERE id = ?", (short_id,))
    db.commit()

    short_row = db.execute(
        """SELECT s.*, u.username as creator_username, u.avatar_url as creator_avatar
           FROM short_films s
           JOIN users u ON s.user_id = u.id
           WHERE s.id = ?""",
        (short_id,),
    ).fetchone()

    if not short_row:
        flash("Short film not found.")
        return redirect(url_for("shorts.index"))

    short_item = dict(short_row)
    video_info = parse_video_source(short_item["video_url"])
    short_item["video_info"] = video_info

    # User reactions breakdown
    rxn_rows = db.execute(
        """SELECT reaction, COUNT(*) as cnt 
           FROM short_film_reactions 
           WHERE short_id = ? 
           GROUP BY reaction""",
        (short_id,),
    ).fetchall()
    reaction_counts = {r[0]: r[1] for r in rxn_rows}

    user_reactions = set()
    if g.user:
        my_rxns = db.execute(
            "SELECT reaction FROM short_film_reactions WHERE short_id = ? AND user_id = ?",
            (short_id, g.user["id"]),
        ).fetchall()
        user_reactions = {r[0] for r in my_rxns}

    # Discussion comments
    comments = db.execute(
        """SELECT c.*, u.username, u.avatar_url
           FROM short_film_comments c
           JOIN users u ON c.user_id = u.id
           WHERE c.short_id = ?
           ORDER BY c.created_at DESC""",
        (short_id,),
    ).fetchall()

    # Related short films by same director or genre
    related = db.execute(
        """SELECT s.*, u.username as creator_username
           FROM short_films s
           JOIN users u ON s.user_id = u.id
           WHERE s.id != ?
           ORDER BY s.views_count DESC
           LIMIT 4""",
        (short_id,),
    ).fetchall()

    return render_template(
        "shorts/detail.html",
        short=short_item,
        video_info=video_info,
        reaction_types=REACTION_TYPES,
        reaction_counts=reaction_counts,
        user_reactions=user_reactions,
        comments=comments,
        related=related,
    )


@bp.route("/<int:short_id>/react", methods=["POST"])
@login_required
def react(short_id):
    """Toggle reaction on a short film."""
    db = get_db()
    reaction = request.form.get("reaction", "").strip().lower()

    valid_types = {t[0] for t in REACTION_TYPES}
    if reaction not in valid_types:
        return jsonify({"error": "Invalid reaction type"}), 400

    existing = db.execute(
        "SELECT id FROM short_film_reactions WHERE short_id = ? AND user_id = ? AND reaction = ?",
        (short_id, g.user["id"], reaction),
    ).fetchone()

    if existing:
        db.execute(
            "DELETE FROM short_film_reactions WHERE short_id = ? AND user_id = ? AND reaction = ?",
            (short_id, g.user["id"], reaction),
        )
        is_active = False
    else:
        db.execute(
            "INSERT INTO short_film_reactions (short_id, user_id, reaction) VALUES (?, ?, ?)",
            (short_id, g.user["id"], reaction),
        )
        is_active = True

    db.commit()

    # Return updated counts
    rxn_rows = db.execute(
        "SELECT reaction, COUNT(*) as cnt FROM short_film_reactions WHERE short_id = ? GROUP BY reaction",
        (short_id,),
    ).fetchall()
    counts = {r[0]: r[1] for r in rxn_rows}
    total = sum(counts.values())

    return jsonify({
        "success": True,
        "reaction": reaction,
        "is_active": is_active,
        "count": counts.get(reaction, 0),
        "total": total,
    })


@bp.route("/<int:short_id>/comment", methods=["POST"])
@login_required
def comment(short_id):
    """Post a discussion comment on a short film with optional video timestamp."""
    db = get_db()
    content = request.form.get("content", "").strip()
    timestamp_mark = request.form.get("timestamp_mark", "").strip()

    if not content:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "Comment cannot be empty."}), 400
        flash("Comment cannot be empty.")
        return redirect(url_for("shorts.detail", short_id=short_id))

    cursor = db.execute(
        """INSERT INTO short_film_comments (short_id, user_id, content, timestamp_mark)
           VALUES (?, ?, ?, ?)""",
        (short_id, g.user["id"], content, timestamp_mark or None),
    )
    db.commit()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "success": True,
            "id": cursor.lastrowid,
            "username": g.user["username"],
            "avatar_url": dict(g.user).get("avatar_url"),
            "content": content,
            "timestamp_mark": timestamp_mark,
            "created_at": "Just now",
        })

    flash("Your reflection has been posted to the discussion thread.")
    return redirect(url_for("shorts.detail", short_id=short_id))


@bp.route("/<int:short_id>/delete", methods=["POST"])
@login_required
def delete(short_id):
    """Delete a short film if creator or admin."""
    db = get_db()
    short = db.execute("SELECT user_id FROM short_films WHERE id = ?", (short_id,)).fetchone()
    if not short:
        flash("Short film not found.")
        return redirect(url_for("shorts.index"))

    if short["user_id"] != g.user["id"] and g.user.get("role") != "admin":
        flash("You do not have permission to delete this short film.")
        return redirect(url_for("shorts.detail", short_id=short_id))

    db.execute("DELETE FROM short_films WHERE id = ?", (short_id,))
    db.commit()
    flash("Short film has been removed.")
    return redirect(url_for("shorts.index"))
