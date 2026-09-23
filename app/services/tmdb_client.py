"""
TMDB (The Movie Database) client.
Get a free API key at: https://www.themoviedb.org/settings/api
Docs: https://developer.themoviedb.org/reference/intro/getting-started
"""

import json
import requests
from flask import current_app

from app.services.settings_store import get_setting

BASE_URL = "https://api.themoviedb.org/3"


def fetch_popular_movies(page=1):
    """Fetch a page of popular movies. Returns a list of dicts ready to insert
    into the `items` table (type='movie')."""
    api_key = get_setting("TMDB_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No TMDB API key set. Add one on the Settings page or set TMDB_API_KEY."
        )

    resp = requests.get(
        f"{BASE_URL}/movie/popular",
        params={"api_key": api_key, "page": page},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    items = []
    for movie in data.get("results", []):
        items.append(
            {
                "type": "movie",
                "external_id": str(movie["id"]),
                "title": movie["title"],
                "genre_tags": "",  # map genre_ids -> names via /genre/movie/list if needed
                "metadata": json.dumps(
                    {
                        "poster_path": movie.get("poster_path"),
                        "overview": movie.get("overview"),
                        "release_date": movie.get("release_date"),
                        "vote_average": movie.get("vote_average"),
                    }
                ),
            }
        )
    return items


def save_items(db, items):
    """Insert a list of item dicts (as produced by the fetch_* functions) into the DB,
    safely skipping any duplicate items. Returns (inserted_count, skipped_count)."""
    inserted = 0
    skipped = 0
    for item in items:
        item_type = item.get("type")
        ext_id = item.get("external_id")
        title = (item.get("title") or "").strip()

        existing = None
        if ext_id:
            existing = db.execute(
                "SELECT id FROM items WHERE type = ? AND external_id = ?",
                (item_type, str(ext_id)),
            ).fetchone()

        if not existing and title:
            existing = db.execute(
                "SELECT id FROM items WHERE type = ? AND LOWER(TRIM(title)) = LOWER(TRIM(?))",
                (item_type, title),
            ).fetchone()

        if existing:
            skipped += 1
            continue

        try:
            db.execute(
                "INSERT INTO items (type, external_id, title, genre_tags, metadata) "
                "VALUES (?, ?, ?, ?, ?)",
                (item_type, ext_id, title, item.get("genre_tags", ""), item.get("metadata", "{}")),
            )
            inserted += 1
        except Exception:
            skipped += 1

    db.commit()
    return inserted, skipped
