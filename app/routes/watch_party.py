from datetime import datetime, timezone
from flask import (
    Blueprint,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from app.auth_utils import login_required
from app.db import get_db
from app.services.video_helper import parse_video_source, resolve_item_video

bp = Blueprint("watch_party", __name__, url_prefix="/watch-parties")

PARTY_EMOJIS = ["🔥", "🍿", "⚽", "🎸", "👏", "😱", "❤️", "🏆"]


@bp.route("/")
@bp.route("")
def index():
    """Lobby / Hub of active and recent Watch Parties across Movies, Music, and Sports."""
    db = get_db()
    active_cat = request.args.get("category", "").strip().lower()
    search_q = request.args.get("q", "").strip()

    sql = """
        SELECT wp.*, u.username as host_username, u.avatar_url as host_avatar,
               i.title as item_title, i.type as item_type, i.metadata as item_metadata,
               sf.title as short_title, sf.thumbnail_url as short_thumb,
               (SELECT COUNT(*) FROM watch_party_members m WHERE m.party_id = wp.id AND m.last_seen >= datetime('now', '-3 minutes')) as active_viewers,
               (SELECT COUNT(*) FROM watch_party_messages msg WHERE msg.party_id = wp.id) as total_messages
        FROM watch_parties wp
        JOIN users u ON wp.host_id = u.id
        LEFT JOIN items i ON wp.item_id = i.id
        LEFT JOIN short_films sf ON wp.short_film_id = sf.id
        WHERE wp.status = 'active'
    """
    params = []

    if active_cat in ("movie", "song", "sports"):
        sql += " AND wp.category = ?"
        params.append(active_cat)

    if search_q:
        sql += " AND (wp.title LIKE ? OR wp.description LIKE ? OR i.title LIKE ?)"
        wild = f"%{search_q}%"
        params.extend([wild, wild, wild])

    sql += " ORDER BY active_viewers DESC, wp.created_at DESC"

    cursor = db.execute(sql, params)
    parties = cursor.fetchall()

    enhanced_parties = []
    for row in parties:
        item = dict(row)
        video_info = parse_video_source(item["video_url"])
        item["video_info"] = video_info
        enhanced_parties.append(item)

    # Catalog items for the "Quick Start" picker
    catalog_movies = db.execute("SELECT id, title FROM items WHERE type = 'movie' ORDER BY title ASC").fetchall()
    catalog_songs = db.execute("SELECT id, title FROM items WHERE type = 'song' ORDER BY title ASC").fetchall()
    catalog_sports = db.execute("SELECT id, title FROM items WHERE type = 'team' ORDER BY title ASC").fetchall()
    community_shorts = db.execute("SELECT id, title FROM short_films ORDER BY created_at DESC LIMIT 10").fetchall()

    return render_template(
        "watch_party/index.html",
        parties=enhanced_parties,
        active_cat=active_cat,
        search_q=search_q,
        catalog_movies=catalog_movies,
        catalog_songs=catalog_songs,
        catalog_sports=catalog_sports,
        community_shorts=community_shorts,
    )


@bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    """Create a new Watch Party for a movie, song, sports match, or community short film."""
    db = get_db()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "movie").strip().lower()
        if category not in ("movie", "song", "sports"):
            category = "movie"

        item_id = request.form.get("item_id", "").strip()
        short_id = request.form.get("short_film_id", "").strip()
        custom_video_url = request.form.get("video_url", "").strip()
        description = request.form.get("description", "").strip()

        item_row = None
        short_row = None
        final_video_url = custom_video_url

        if item_id and item_id.isdigit():
            item_row = db.execute("SELECT * FROM items WHERE id = ?", (int(item_id),)).fetchone()
            if item_row:
                item_dict = dict(item_row)
                if not title:
                    title = f"{item_dict['title']} Watch Party 🍿"
                if not final_video_url:
                    parsed = resolve_item_video(item_dict, db=db)
                    final_video_url = parsed["raw_url"]
                # Infer category from item type
                if item_dict["type"] == "movie":
                    category = "movie"
                elif item_dict["type"] == "song":
                    category = "song"
                elif item_dict["type"] == "team":
                    category = "sports"

        elif short_id and short_id.isdigit():
            short_row = db.execute("SELECT * FROM short_films WHERE id = ?", (int(short_id),)).fetchone()
            if short_row:
                if not title:
                    title = f"Premiere Watch Party: {short_row['title']} 🎬"
                if not final_video_url:
                    final_video_url = short_row["video_url"]
                category = "movie"

        if not title:
            title = f"{category.capitalize()} Watch Lounge 🎉"

        if not final_video_url:
            # Fallback based on category
            if category == "movie":
                final_video_url = "https://www.youtube.com/watch?v=YoHD9XEInc0"
            elif category == "song":
                final_video_url = "https://www.youtube.com/watch?v=4NRXx6U8ABQ"
            else:
                final_video_url = "https://www.youtube.com/watch?v=qC50WbA-u3o"

        parsed_video = parse_video_source(final_video_url)

        cursor = db.execute(
            """INSERT INTO watch_parties 
               (host_id, item_id, short_film_id, category, title, description, video_url, video_type, status, is_playing, current_time)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', 1, 0.0)""",
            (
                g.user["id"],
                int(item_id) if item_id and item_id.isdigit() else None,
                int(short_id) if short_id and short_id.isdigit() else None,
                category,
                title,
                description or "Welcome to our live watch party! Enjoy the stream and chat together.",
                parsed_video["raw_url"],
                parsed_video["video_type"],
            ),
        )
        party_id = cursor.lastrowid

        # Join the host immediately
        db.execute(
            "INSERT OR REPLACE INTO watch_party_members (party_id, user_id, last_seen) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (party_id, g.user["id"]),
        )
        # Welcome message
        db.execute(
            "INSERT INTO watch_party_messages (party_id, user_id, content) VALUES (?, ?, ?)",
            (party_id, g.user["id"], "🎉 Watch Party opened! Welcome everyone, feel free to react and chat!"),
        )
        db.commit()

        flash(f"🎉 Watch Party '{title}' is now live!")
        return redirect(url_for("watch_party.room", party_id=party_id))

    # Pre-fills for GET request
    prefill_item_id = request.args.get("item_id", "").strip()
    prefill_short_id = request.args.get("short_id", "").strip()
    prefill_category = request.args.get("category", "movie").strip().lower()

    prefill_item = None
    if prefill_item_id and prefill_item_id.isdigit():
        prefill_item = db.execute("SELECT * FROM items WHERE id = ?", (int(prefill_item_id),)).fetchone()
        if prefill_item:
            if prefill_item["type"] == "movie":
                prefill_category = "movie"
            elif prefill_item["type"] == "song":
                prefill_category = "song"
            elif prefill_item["type"] == "team":
                prefill_category = "sports"

    prefill_short = None
    if prefill_short_id and prefill_short_id.isdigit():
        prefill_short = db.execute("SELECT * FROM short_films WHERE id = ?", (int(prefill_short_id),)).fetchone()

    catalog_movies = db.execute("SELECT id, title FROM items WHERE type = 'movie' ORDER BY title ASC").fetchall()
    catalog_songs = db.execute("SELECT id, title FROM items WHERE type = 'song' ORDER BY title ASC").fetchall()
    catalog_sports = db.execute("SELECT id, title FROM items WHERE type = 'team' ORDER BY title ASC").fetchall()
    community_shorts = db.execute("SELECT id, title FROM short_films ORDER BY created_at DESC LIMIT 10").fetchall()

    return render_template(
        "watch_party/create.html",
        prefill_category=prefill_category,
        prefill_item=prefill_item,
        prefill_short=prefill_short,
        catalog_movies=catalog_movies,
        catalog_songs=catalog_songs,
        catalog_sports=catalog_sports,
        community_shorts=community_shorts,
    )


@bp.route("/<int:party_id>")
def room(party_id):
    """The interactive live Watch Party Theater Room."""
    db = get_db()

    party_row = db.execute(
        """SELECT wp.*, u.username as host_username, u.avatar_url as host_avatar,
                  i.title as item_title, i.type as item_type, i.metadata as item_metadata,
                  sf.title as short_title, sf.director_name as short_director
           FROM watch_parties wp
           JOIN users u ON wp.host_id = u.id
           LEFT JOIN items i ON wp.item_id = i.id
           LEFT JOIN short_films sf ON wp.short_film_id = sf.id
           WHERE wp.id = ?""",
        (party_id,),
    ).fetchone()

    if not party_row:
        flash("Watch Party not found or has been ended.")
        return redirect(url_for("watch_party.index"))

    party = dict(party_row)
    video_info = parse_video_source(party["video_url"])
    party["video_info"] = video_info

    # Mark user as present if logged in
    if g.user:
        db.execute(
            "INSERT OR REPLACE INTO watch_party_members (party_id, user_id, last_seen) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (party_id, g.user["id"]),
        )
        db.commit()

    # Load initial messages (last 60)
    messages = db.execute(
        """SELECT m.*, u.username, u.avatar_url,
                  CASE WHEN m.user_id = ? THEN 1 ELSE 0 END as is_host_msg
           FROM watch_party_messages m
           JOIN users u ON m.user_id = u.id
           WHERE m.party_id = ?
           ORDER BY m.id ASC
           LIMIT 60""",
        (party["host_id"], party_id),
    ).fetchall()

    # Active attendees
    active_members = db.execute(
        """SELECT u.id, u.username, u.avatar_url,
                  CASE WHEN u.id = ? THEN 1 ELSE 0 END as is_host
           FROM watch_party_members m
           JOIN users u ON m.user_id = u.id
           WHERE m.party_id = ? AND m.last_seen >= datetime('now', '-3 minutes')
           ORDER BY is_host DESC, m.last_seen DESC""",
        (party["host_id"], party_id),
    ).fetchall()

    is_host = g.user and g.user["id"] == party["host_id"]

    return render_template(
        "watch_party/room.html",
        party=party,
        video_info=video_info,
        messages=messages,
        active_members=active_members,
        party_emojis=PARTY_EMOJIS,
        is_host=is_host,
    )


@bp.route("/<int:party_id>/message", methods=["POST"])
@login_required
def post_message(party_id):
    """Post a live chat message to the Watch Party room."""
    db = get_db()
    content = request.form.get("content", "").strip()
    marker = request.form.get("timestamp_marker")

    if not content:
        return jsonify({"error": "Message cannot be empty."}), 400

    timestamp_val = None
    if marker:
        try:
            timestamp_val = float(marker)
        except (ValueError, TypeError):
            pass

    cursor = db.execute(
        "INSERT INTO watch_party_messages (party_id, user_id, content, timestamp_marker) VALUES (?, ?, ?, ?)",
        (party_id, g.user["id"], content, timestamp_val),
    )
    # Update active presence
    db.execute(
        "INSERT OR REPLACE INTO watch_party_members (party_id, user_id, last_seen) VALUES (?, ?, CURRENT_TIMESTAMP)",
        (party_id, g.user["id"]),
    )
    db.commit()

    return jsonify({
        "success": True,
        "message": {
            "id": cursor.lastrowid,
            "username": g.user["username"],
            "avatar_url": dict(g.user).get("avatar_url"),
            "content": content,
            "timestamp_marker": timestamp_val,
            "created_at": "Just now",
        },
    })


@bp.route("/<int:party_id>/react", methods=["POST"])
@login_required
def post_reaction(party_id):
    """Fire a reaction burst in the Watch Party room (float animation)."""
    db = get_db()
    emoji = request.form.get("emoji", "").strip()
    if not emoji or emoji not in PARTY_EMOJIS:
        emoji = "🔥"

    cursor = db.execute(
        "INSERT INTO watch_party_reactions (party_id, user_id, emoji) VALUES (?, ?, ?)",
        (party_id, g.user["id"], emoji),
    )
    db.commit()

    return jsonify({
        "success": True,
        "reaction": {
            "id": cursor.lastrowid,
            "emoji": emoji,
            "username": g.user["username"],
        },
    })


@bp.route("/<int:party_id>/sync")
def sync(party_id):
    """
    Lightweight polling endpoint (called every 2-3s) that returns:
    - New messages since last_msg_id
    - New reaction bursts since last_rxn_id
    - Host playback state (is_playing, current_time)
    - Active viewers count & member list
    """
    db = get_db()
    last_msg_id = request.args.get("last_msg_id", 0, type=int)
    last_rxn_id = request.args.get("last_rxn_id", 0, type=int)

    # Update current user's presence heartbeat
    if g.user:
        db.execute(
            "INSERT OR REPLACE INTO watch_party_members (party_id, user_id, last_seen) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (party_id, g.user["id"]),
        )
        db.commit()

    party_row = db.execute(
        "SELECT id, host_id, status, is_playing, current_time, updated_at FROM watch_parties WHERE id = ?",
        (party_id,),
    ).fetchone()

    if not party_row:
        return jsonify({"status": "ended", "error": "Party not found"}), 404

    # Fetch new messages
    new_msgs = db.execute(
        """SELECT m.id, m.content, m.timestamp_marker, m.created_at, u.username, u.avatar_url,
                  CASE WHEN m.user_id = ? THEN 1 ELSE 0 END as is_host_msg
           FROM watch_party_messages m
           JOIN users u ON m.user_id = u.id
           WHERE m.party_id = ? AND m.id > ?
           ORDER BY m.id ASC
           LIMIT 30""",
        (party_row["host_id"], party_id, last_msg_id),
    ).fetchall()

    # Fetch new reaction bursts
    new_rxns = db.execute(
        """SELECT r.id, r.emoji, r.created_at, u.username
           FROM watch_party_reactions r
           JOIN users u ON r.user_id = u.id
           WHERE r.party_id = ? AND r.id > ?
           ORDER BY r.id ASC
           LIMIT 20""",
        (party_id, last_rxn_id),
    ).fetchall()

    # Active members
    active_members = db.execute(
        """SELECT u.id, u.username, u.avatar_url,
                  CASE WHEN u.id = ? THEN 1 ELSE 0 END as is_host
           FROM watch_party_members m
           JOIN users u ON m.user_id = u.id
           WHERE m.party_id = ? AND m.last_seen >= datetime('now', '-3 minutes')
           ORDER BY is_host DESC, m.last_seen DESC""",
        (party_row["host_id"], party_id),
    ).fetchall()

    return jsonify({
        "status": party_row["status"],
        "is_playing": bool(party_row["is_playing"]),
        "current_time": party_row["current_time"],
        "updated_at": party_row["updated_at"],
        "is_host": bool(g.user and g.user["id"] == party_row["host_id"]),
        "viewers_count": len(active_members),
        "members": [dict(m) for m in active_members],
        "messages": [dict(m) for m in new_msgs],
        "reactions": [dict(r) for r in new_rxns],
    })


@bp.route("/<int:party_id>/control", methods=["POST"])
@login_required
def control(party_id):
    """Host-only control endpoint to broadcast play/pause/seek synchronization."""
    db = get_db()
    party = db.execute("SELECT host_id FROM watch_parties WHERE id = ?", (party_id,)).fetchone()
    if not party or party["host_id"] != g.user["id"]:
        return jsonify({"error": "Host controls only."}), 403

    is_playing = request.form.get("is_playing")
    current_time = request.form.get("current_time")

    updates = []
    params = []

    if is_playing is not None:
        val = 1 if str(is_playing).lower() in ("1", "true") else 0
        updates.append("is_playing = ?")
        params.append(val)

    if current_time is not None:
        try:
            t = float(current_time)
            updates.append("current_time = ?")
            params.append(t)
        except (ValueError, TypeError):
            pass

    if updates:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(party_id)
        db.execute(f"UPDATE watch_parties SET {', '.join(updates)} WHERE id = ?", params)
        db.commit()

    return jsonify({"success": True})


@bp.route("/<int:party_id>/end", methods=["POST"])
@login_required
def end_party(party_id):
    """End or close a Watch Party room."""
    db = get_db()
    party = db.execute("SELECT host_id, title FROM watch_parties WHERE id = ?", (party_id,)).fetchone()
    if not party:
        flash("Party not found.")
        return redirect(url_for("watch_party.index"))

    if party["host_id"] != g.user["id"] and g.user.get("role") != "admin":
        flash("Only the room host can end this watch party.")
        return redirect(url_for("watch_party.room", party_id=party_id))

    db.execute("UPDATE watch_parties SET status = 'ended', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (party_id,))
    db.commit()
    flash(f"Watch party '{party['title']}' has been ended.")
    return redirect(url_for("watch_party.index"))
