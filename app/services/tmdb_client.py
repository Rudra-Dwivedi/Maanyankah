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


TMDB_GENRES = {
    28: "Action",
    12: "Adventure",
    16: "Animation",
    35: "Comedy",
    80: "Crime",
    99: "Documentary",
    18: "Drama",
    10751: "Family",
    14: "Fantasy",
    36: "History",
    27: "Horror",
    10402: "Music",
    9648: "Mystery",
    10749: "Romance",
    878: "Sci-Fi",
    10770: "TV Movie",
    53: "Thriller",
    10752: "War",
    37: "Western",
}


def fetch_popular_movies(page=1, pages=1):
    """Fetch popular movies from TMDB across one or more pages.
    Each page contains 20 movies. E.g. pages=3 fetches 60 movies.
    Returns a list of dicts ready to insert into the `items` table."""
    api_key = get_setting("TMDB_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No TMDB API key set. Add one on the Settings page or set TMDB_API_KEY."
        )

    # Determine range of pages to fetch
    start_page = page
    end_page = start_page + max(1, pages) - 1

    items = []
    seen_ids = set()

    for p in range(start_page, end_page + 1):
        try:
            resp = requests.get(
                f"{BASE_URL}/movie/popular",
                params={"api_key": api_key, "page": p},
                timeout=12,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            # If at least some movies were fetched in prior pages, return what we have
            if items:
                break
            raise e

        results = data.get("results", [])
        if not results:
            break

        for movie in results:
            m_id = str(movie.get("id"))
            if m_id in seen_ids:
                continue
            seen_ids.add(m_id)

            # Map TMDB genre IDs to human-readable names
            genre_ids = movie.get("genre_ids", [])
            genre_names = [TMDB_GENRES[gid] for gid in genre_ids if gid in TMDB_GENRES]
            genre_tags = ",".join(genre_names)

            items.append(
                {
                    "type": "movie",
                    "external_id": m_id,
                    "title": movie.get("title", "").strip(),
                    "genre_tags": genre_tags,
                    "metadata": json.dumps(
                        {
                            "poster_path": movie.get("poster_path"),
                            "overview": movie.get("overview", ""),
                            "release_date": movie.get("release_date", ""),
                            "vote_average": movie.get("vote_average", 0),
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
