import json
import os
import sqlite3

from flask import current_app, g
from werkzeug.security import generate_password_hash

DEFAULT_CATALOG_ITEMS = [
    ("movie", "Inception", "sci-fi,thriller", "https://m.media-amazon.com/images/M/MV5BMjAxMzY3NjcxNF5BMl5BanBnXkFtZTcwNTI5OTM0Mw@@._V1_FMjpg_UX1000_.jpg"),
    ("movie", "The Dark Knight", "action,crime", "https://m.media-amazon.com/images/M/MV5BMTMxNTMwODM0NF5BMl5BanBnXkFtZTcwODAyMTk2Mw@@._V1_FMjpg_UX1000_.jpg"),
    ("movie", "Interstellar", "sci-fi,adventure,drama", "https://m.media-amazon.com/images/M/MV5BYzdjMDAxZGItMjI2My00ODA1LTlkNzItOWFjMDU5ZDJlYWY3XkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg"),
    ("movie", "La La Land", "musical,romance", "https://m.media-amazon.com/images/M/MV5BMDllYjliOTUtMDJjZC00ODIzLWJmNGMtOWI2NzQxMjA2NzdlXkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg"),
    ("movie", "Parasite", "thriller,drama", "https://m.media-amazon.com/images/M/MV5BYjk1Y2U4MjQtY2ZiNS00OWQyLWI3MmYtZWUwNmRjYWRiNWNhXkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg"),
    ("movie", "Pulp Fiction", "crime,drama", "https://m.media-amazon.com/images/M/MV5BYTViYTE3NWQtYjhmYS00ODBlLWIxOTEtNmNjOWEyOWYxZTM4XkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg"),
    ("movie", "The Grand Budapest Hotel", "comedy,drama", "https://m.media-amazon.com/images/M/MV5BMzM5NjUxOTEyMl5BMl5BanBnXkFtZTgwNjEyMDM0MDE@._V1_FMjpg_UX1000_.jpg"),
    ("movie", "Whiplash", "drama,music", "https://m.media-amazon.com/images/M/MV5BOTA5NDZlZGUtMjAxOS00YTRkLTkwYmMtYWQ0NWEwZDZiNjEzXkEyXkFqcGc@._V1_FMjpg_UX1000_.jpg"),
    ("song", "Blinding Lights — The Weeknd", "pop,synthwave", "https://is1-ssl.mzstatic.com/image/thumb/Music115/v4/61/e7/3f/61e73f94-018d-5f50-50ec-8521952bc72e/20UM1IM11629.rgb.jpg/1000x1000bb.jpg"),
    ("song", "Starboy — The Weeknd", "r&b,pop", "https://is1-ssl.mzstatic.com/image/thumb/Music125/v4/4a/5b/4b/4a5b4be4-eb89-e85d-85fa-398b58fae473/16UMGIM81498.rgb.jpg/1000x1000bb.jpg"),
    ("song", "HUMBLE. — Kendrick Lamar", "hip-hop", "https://is1-ssl.mzstatic.com/image/thumb/Music112/v4/ab/16/ef/ab16efe9-e7f1-66ec-021c-5592a23f0f9e/17UMGIM88793.rgb.jpg/1000x1000bb.jpg"),
    ("song", "Lose Yourself — Eminem", "hip-hop,rap", "https://is1-ssl.mzstatic.com/image/thumb/Music114/v4/ce/68/73/ce68735d-8580-c08c-e67c-9b57c7c00e12/00602547101569.rgb.jpg/1000x1000bb.jpg"),
    ("song", "Bohemian Rhapsody — Queen", "rock", "https://is1-ssl.mzstatic.com/image/thumb/Music115/v4/4d/08/2a/4d082a9e-7898-1aa1-a02f-339810058d9e/14DMGIM05632.rgb.jpg/1000x1000bb.jpg"),
    ("song", "Hotel California — Eagles", "rock,classic", "https://is1-ssl.mzstatic.com/image/thumb/Music118/v4/a4/c8/f4/a4c8f498-8b89-63ff-c94b-486127bcfb92/081227976216.jpg/1000x1000bb.jpg"),
    ("song", "As It Was — Harry Styles", "pop", "https://is1-ssl.mzstatic.com/image/thumb/Music126/v4/2a/19/fb/2a19fb85-2f70-9e44-f2a9-82abe679b88e/886449990061.jpg/1000x1000bb.jpg"),
    ("song", "Levitating — Dua Lipa", "pop,dance", "https://is1-ssl.mzstatic.com/image/thumb/Music116/v4/6c/11/d6/6c11d681-aa3a-d59e-4c2e-f77e181026ab/190295092665.jpg/1000x1000bb.jpg"),
    ("song", "Get Lucky — Daft Punk", "disco,funk,dance", "https://is1-ssl.mzstatic.com/image/thumb/Music115/v4/10/72/7b/10727b13-8cfb-d98c-8f9d-16fce8f01b0f/886443927087.jpg/1000x1000bb.jpg"),
    ("team", "Mumbai Indians", "cricket,IPL", "https://r2.thesportsdb.com/images/media/team/badge/l40j8p1487678631.png"),
    ("team", "Real Madrid", "football,La Liga", "https://r2.thesportsdb.com/images/media/team/badge/vwvwrw1473502969.png"),
    ("team", "Los Angeles Lakers", "basketball,NBA", "https://r2.thesportsdb.com/images/media/team/badge/d8uoxw1714254511.png"),
    ("team", "Chennai Super Kings", "cricket,IPL", "https://r2.thesportsdb.com/images/media/team/badge/okceh51487601098.png"),
    ("team", "Manchester United", "football,Premier League", "https://r2.thesportsdb.com/images/media/team/badge/xzqdr11517660252.png"),
]


def get_db():
    """Return a request-scoped SQLite connection with row access by column name."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE_PATH"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    """Create tables from schema.sql if they don't exist yet, run migrations, and seed initial data."""
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE_PATH"])
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(schema_path, "r", encoding="utf-8") as f:
            db.executescript(f.read())

        cursor = db.cursor()

        # Migration: ensure users table has is_active and avatar_url columns
        cursor.execute("PRAGMA table_info(users)")
        user_columns = [row[1] for row in cursor.fetchall()]
        if "is_active" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
        if "avatar_url" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
        if "bio" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN bio TEXT")
        if "last_login" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN last_login TIMESTAMP")

        # Migration: ensure posts table has is_pinned column
        cursor.execute("PRAGMA table_info(posts)")
        post_columns = [row[1] for row in cursor.fetchall()]
        if "is_pinned" not in post_columns:
            cursor.execute("ALTER TABLE posts ADD COLUMN is_pinned INTEGER NOT NULL DEFAULT 0")

        # Idempotently seed catalog items
        for item_type, title, tags, img_url in DEFAULT_CATALOG_ITEMS:
            cursor.execute("SELECT id FROM items WHERE title = ?", (title,))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO items (type, title, genre_tags, metadata) VALUES (?, ?, ?, ?)",
                    (item_type, title, tags, json.dumps({"image_url": img_url})),
                )

        # Seed initial curated collections if collections table is empty
        cursor.execute("SELECT COUNT(*) FROM collections")
        if cursor.fetchone()[0] == 0:
            cursor.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1")
            first_user = cursor.fetchone()
            if first_user:
                uid = first_user[0]
                # Collection 1: Essential Cinematic Journeys
                cursor.execute(
                    "INSERT INTO collections (user_id, title, description, is_public) VALUES (?, ?, ?, 1)",
                    (uid, "Essential Cinematic Journeys", "Mind-bending masterpieces and modern cinema cornerstones."),
                )
                cid1 = cursor.lastrowid
                for movie_title in ["Inception", "Interstellar", "The Dark Knight", "Parasite"]:
                    cursor.execute("SELECT id FROM items WHERE title = ?", (movie_title,))
                    item_row = cursor.fetchone()
                    if item_row:
                        cursor.execute("INSERT OR IGNORE INTO collection_items (collection_id, item_id) VALUES (?, ?)", (cid1, item_row[0]))

                # Collection 2: Night Drive & Synth Vibes
                cursor.execute(
                    "INSERT INTO collections (user_id, title, description, is_public) VALUES (?, ?, ?, 1)",
                    (uid, "Night Drive & High Energy", "Electronic beats, modern disco, and timeless anthems."),
                )
                cid2 = cursor.lastrowid
                for song_title in ["Blinding Lights — The Weeknd", "Starboy — The Weeknd", "Get Lucky — Daft Punk", "Bohemian Rhapsody — Queen"]:
                    cursor.execute("SELECT id FROM items WHERE title = ?", (song_title,))
                    item_row = cursor.fetchone()
                    if item_row:
                        cursor.execute("INSERT OR IGNORE INTO collection_items (collection_id, item_id) VALUES (?, ?)", (cid2, item_row[0]))

        # Optional auto-provision of admin via environment variables (e.g. Railway Variables)
        admin_user = os.environ.get("ADMIN_USERNAME", "").strip()
        admin_pass = os.environ.get("ADMIN_PASSWORD", "").strip()
        if admin_user and admin_pass:
            admin_email = os.environ.get("ADMIN_EMAIL", f"{admin_user}@fannetwork.local").strip()
            cursor.execute("SELECT id, role FROM users WHERE username = ?", (admin_user,))
            existing = cursor.fetchone()
            if not existing:
                cursor.execute(
                    "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, 'admin')",
                    (admin_user, admin_email, generate_password_hash(admin_pass)),
                )
            elif existing[1] != "admin":
                cursor.execute("UPDATE users SET role = 'admin' WHERE id = ?", (existing[0],))

        db.commit()
        db.close()


def register_db(app):
    app.teardown_appcontext(close_db)
    init_db(app)
