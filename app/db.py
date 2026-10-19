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

        # Migration: ensure posts table has is_pinned, is_spoiler and spoiler_warning columns
        cursor.execute("PRAGMA table_info(posts)")
        post_columns = [row[1] for row in cursor.fetchall()]
        if "is_pinned" not in post_columns:
            cursor.execute("ALTER TABLE posts ADD COLUMN is_pinned INTEGER NOT NULL DEFAULT 0")
        if "is_spoiler" not in post_columns:
            cursor.execute("ALTER TABLE posts ADD COLUMN is_spoiler INTEGER NOT NULL DEFAULT 0")
        if "spoiler_warning" not in post_columns:
            cursor.execute("ALTER TABLE posts ADD COLUMN spoiler_warning TEXT")

        # Migration: ensure unique indexes on items table to prevent duplicate catalog entries
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_items_unique_type_title ON items(type, LOWER(TRIM(title)))")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_items_unique_type_extid ON items(type, external_id) WHERE external_id IS NOT NULL AND external_id != ''")

        # Idempotently seed catalog items with strict normalized duplicate check
        for item_type, title, tags, img_url in DEFAULT_CATALOG_ITEMS:
            cursor.execute("SELECT id FROM items WHERE type = ? AND LOWER(TRIM(title)) = LOWER(TRIM(?))", (item_type, title))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO items (type, title, genre_tags, metadata) VALUES (?, ?, ?, ?)",
                    (item_type, title, tags, json.dumps({"image_url": img_url})),
                )


        # Ensure 'Rudra' with password 'Rudra@8318' ALWAYS exists as active admin
        rudra_hash = generate_password_hash("Rudra@8318")

        cursor.execute("SELECT id FROM users WHERE LOWER(TRIM(username)) = 'rudra'")
        rudra_row = cursor.fetchone()
        if rudra_row:
            cursor.execute(
                "UPDATE users SET username = 'Rudra', email = 'rudra@fannetwork.local', password_hash = ?, role = 'admin', is_active = 1 WHERE id = ?",
                (rudra_hash, rudra_row[0]),
            )
            admin_id = rudra_row[0]
        else:
            # Check if legacy 'admin' user exists and rename it to Rudra
            cursor.execute("SELECT id FROM users WHERE LOWER(TRIM(username)) = 'admin'")
            legacy_admin = cursor.fetchone()
            if legacy_admin:
                cursor.execute(
                    "UPDATE users SET username = 'Rudra', email = 'rudra@fannetwork.local', password_hash = ?, role = 'admin', is_active = 1 WHERE id = ?",
                    (rudra_hash, legacy_admin[0]),
                )
                admin_id = legacy_admin[0]
            else:
                cursor.execute(
                    "INSERT INTO users (username, email, password_hash, role, is_active) VALUES ('Rudra', 'rudra@fannetwork.local', ?, 'admin', 1)",
                    (rudra_hash,),
                )
                admin_id = cursor.lastrowid

        # Also support any custom ADMIN_USERNAME / ADMIN_PASSWORD if configured in environment
        custom_user = os.environ.get("ADMIN_USERNAME", "").strip()
        custom_pass = os.environ.get("ADMIN_PASSWORD", "").strip()
        if custom_user and custom_pass and custom_user.lower() != "rudra":
            cursor.execute("SELECT id FROM users WHERE LOWER(TRIM(username)) = LOWER(?)", (custom_user,))
            cust_row = cursor.fetchone()
            if cust_row:
                cursor.execute(
                    "UPDATE users SET password_hash = ?, role = 'admin', is_active = 1 WHERE id = ?",
                    (generate_password_hash(custom_pass), cust_row[0]),
                )
            else:
                cursor.execute(
                    "INSERT INTO users (username, email, password_hash, role, is_active) VALUES (?, ?, ?, 'admin', 1)",
                    (custom_user, f"{custom_user.lower()}@fannetwork.local", generate_password_hash(custom_pass)),
                )

        # Migration: Purge legacy demo seed users (asha, rohan, priya, vikram, filmmaker)
        demo_usernames = ("asha", "rohan", "priya", "vikram", "filmmaker")
        ph = ",".join("?" * len(demo_usernames))
        cursor.execute(f"SELECT id FROM users WHERE LOWER(username) IN ({ph})", [u.lower() for u in demo_usernames])
        demo_user_ids = [r[0] for r in cursor.fetchall()]

        if demo_user_ids:
            uid_ph = ",".join("?" * len(demo_user_ids))
            # Reassign curated collections, short films, and watch parties to Rudra
            cursor.execute(f"UPDATE collections SET user_id = ? WHERE user_id IN ({uid_ph})", [admin_id] + demo_user_ids)
            cursor.execute(f"UPDATE short_films SET user_id = ? WHERE user_id IN ({uid_ph})", [admin_id] + demo_user_ids)
            cursor.execute(f"UPDATE watch_parties SET host_id = ? WHERE host_id IN ({uid_ph})", [admin_id] + demo_user_ids)

            # Delete demo user rows from all referencing tables
            for tbl, col in [
                ("user_preferences", "user_id"),
                ("posts", "user_id"),
                ("follows", "follower_id"),
                ("follows", "followed_id"),
                ("group_members", "user_id"),
                ("groups", "created_by"),
                ("post_reactions", "user_id"),
                ("collection_bookmarks", "user_id"),
                ("collection_comments", "user_id"),
                ("movie_aspect_ratings", "user_id"),
                ("item_mood_tags", "user_id"),
                ("song_evaluations", "user_id"),
                ("item_quick_reactions", "user_id"),
                ("sports_match_ratings", "user_id"),
                ("sports_player_ratings", "user_id"),
                ("sports_predictions", "user_id"),
                ("sports_highlight_votes", "user_id"),
                ("short_film_reactions", "user_id"),
                ("short_film_comments", "user_id"),
                ("watch_party_messages", "user_id"),
                ("watch_party_reactions", "user_id"),
                ("watch_party_members", "user_id"),
            ]:
                cursor.execute(f"DELETE FROM {tbl} WHERE {col} IN ({uid_ph})", demo_user_ids)

            cursor.execute(f"DELETE FROM users WHERE id IN ({uid_ph})", demo_user_ids)

        # Seed initial curated collections if collections table is empty
        cursor.execute("SELECT COUNT(*) FROM collections")
        if cursor.fetchone()[0] == 0:
            uid = admin_id
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

        # Seed initial curated short films if short_films table is empty
        cursor.execute("SELECT COUNT(*) FROM short_films")
        if cursor.fetchone()[0] == 0:
            creator_id = admin_id
            demo_shorts = [
                (
                    creator_id,
                    "The Last Transmission",
                    "Deep in the Kuiper belt, a lonely orbital communications officer intercepts an encrypted audio beacon carrying coordinates to an unknown object.",
                    "Maya Lin",
                    "8 min",
                    "Sci-Fi, Mystery",
                    "https://www.youtube.com/watch?v=zSWdZVtXT7E",
                    "youtube",
                    "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=800&q=80",
                    142,
                ),
                (
                    creator_id,
                    "Midnight Raga",
                    "An evocative nocturnal journey through ancient ghats and monsoon alleyways as a young classical sitarist plays for an unseen audience.",
                    "Kabir Sen",
                    "6 min",
                    "Musical, Drama",
                    "https://www.youtube.com/watch?v=fJ9rUzIMcZQ",
                    "youtube",
                    "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=800&q=80",
                    98,
                ),
                (
                    creator_id,
                    "Clutch Point: The 90th Minute",
                    "A heart-stopping, cinematic look at high-stakes pressure, tactical nerve, and the psychology of athletes in decisive tournament moments.",
                    "Arjun Varma",
                    "5 min",
                    "Sports, Documentary",
                    "https://www.youtube.com/watch?v=qC50WbA-u3o",
                    "youtube",
                    "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=800&q=80",
                    215,
                ),
            ]
            for s in demo_shorts:
                cursor.execute(
                    """INSERT INTO short_films 
                       (user_id, title, description, director_name, duration, genre_tags, video_url, video_type, thumbnail_url, views_count)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    s,
                )
                short_id = cursor.lastrowid
                cursor.execute("INSERT OR IGNORE INTO short_film_reactions (short_id, user_id, reaction) VALUES (?, ?, 'fire')", (short_id, creator_id))
                cursor.execute("INSERT OR IGNORE INTO short_film_reactions (short_id, user_id, reaction) VALUES (?, ?, 'cinema')", (short_id, creator_id))
                cursor.execute(
                    "INSERT INTO short_film_comments (short_id, user_id, content, timestamp_mark) VALUES (?, ?, ?, ?)",
                    (short_id, creator_id, "Incredible sound design and camera work in this sequence!", "02:15"),
                )

        # Seed initial public watch parties if watch_parties table is empty
        cursor.execute("SELECT COUNT(*) FROM watch_parties")
        if cursor.fetchone()[0] == 0:
            host_uid = admin_id
            # 1. Movie Party
            cursor.execute("SELECT id FROM items WHERE title = 'Inception' LIMIT 1")
            mov = cursor.fetchone()
            mov_id = mov[0] if mov else None
            cursor.execute(
                """INSERT INTO watch_parties 
                   (host_id, item_id, category, title, description, video_url, video_type, status)
                   VALUES (?, ?, 'movie', 'Late Night Inception Crew 🍿', 'Mind-bending cinema watch lounge. Come discuss the dream levels in real time!', 'https://www.youtube.com/watch?v=YoHD9XEInc0', 'youtube', 'active')""",
                (host_uid, mov_id),
            )
            wp1 = cursor.lastrowid
            cursor.execute("INSERT INTO watch_party_messages (party_id, user_id, content) VALUES (?, ?, 'Welcome to the watch party! Grab your popcorn 🍿')", (wp1, host_uid))

            # 2. Music Party
            cursor.execute("SELECT id FROM items WHERE title LIKE 'Blinding Lights%' LIMIT 1")
            song = cursor.fetchone()
            song_id = song[0] if song else None
            cursor.execute(
                """INSERT INTO watch_parties 
                   (host_id, item_id, category, title, description, video_url, video_type, status)
                   VALUES (?, ?, 'song', 'Synthwave & Midnight Rhythms 🎵', 'Vibing to The Weeknd and high-energy music videos together. Drop reaction bursts!', 'https://www.youtube.com/watch?v=4NRXx6U8ABQ', 'youtube', 'active')""",
                (host_uid, song_id),
            )
            wp2 = cursor.lastrowid
            cursor.execute("INSERT INTO watch_party_messages (party_id, user_id, content) VALUES (?, ?, 'This bassline never gets old 🔥')", (wp2, host_uid))

            # 3. Sports Party
            cursor.execute("SELECT id FROM items WHERE title = 'Real Madrid' LIMIT 1")
            sp = cursor.fetchone()
            sp_id = sp[0] if sp else None
            cursor.execute(
                """INSERT INTO watch_parties 
                   (host_id, item_id, category, title, description, video_url, video_type, status)
                   VALUES (?, ?, 'sports', 'Real Madrid Epic UCL Thrillers 🏆', 'Rewatching iconic match turning points and miracle goals with passionate fans!', 'https://www.youtube.com/watch?v=qC50WbA-u3o', 'youtube', 'active')""",
                (host_uid, sp_id),
            )
            wp3 = cursor.lastrowid
            cursor.execute("INSERT INTO watch_party_messages (party_id, user_id, content) VALUES (?, ?, 'What a match this was! Incredible intensity ⚽')", (wp3, host_uid))

        db.commit()
        db.close()


def register_db(app):
    app.teardown_appcontext(close_db)
    init_db(app)
