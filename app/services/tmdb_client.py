"""
TMDB (The Movie Database) client.
Get a free API key at: https://www.themoviedb.org/settings/api
Docs: https://developer.themoviedb.org/reference/intro/getting-started
"""

import json
import requests
from flask import current_app

from app.services.settings_store import get_setting, set_setting

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


class TMDBFetchResult(list):
    """List of movie items with attached pagination metadata."""
    def __init__(self, items, start_page, end_page):
        super().__init__(items)
        self.start_page = start_page
        self.end_page = end_page
        self.pages_fetched = max(0, end_page - start_page + 1) if end_page >= start_page else 0


def get_tmdb_page_cursor():
    """Return the last TMDB page fetched (stored in settings table), default 0."""
    try:
        val = get_setting("TMDB_LAST_PAGE", fallback="0")
        if val and str(val).strip().isdigit():
            return int(str(val).strip())
        return 0
    except Exception:
        return 0


def advance_tmdb_page_cursor(page):
    """Set the last TMDB page fetched."""
    try:
        val = max(1, int(page))
        set_setting("TMDB_LAST_PAGE", str(val))
    except Exception as e:
        current_app.logger.warning(f"Could not advance TMDB page cursor: {e}")


def reset_tmdb_page_cursor():
    """Reset the TMDB page cursor back to 0 (so next fetch starts at page 1)."""
    try:
        set_setting("TMDB_LAST_PAGE", "0")
    except Exception as e:
        current_app.logger.warning(f"Could not reset TMDB page cursor: {e}")


def fetch_popular_movies(page=None, pages=1, auto_advance=False):
    """Fetch popular movies from TMDB across one or more pages.
    If `page` is None, automatically starts from the next unseen page (cursor + 1).
    Each page contains 20 movies. E.g. pages=3 fetches up to 60 movies.
    Returns a TMDBFetchResult (inherits list) of dicts ready to insert into `items`."""
    api_key = get_setting("TMDB_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No TMDB API key set. Add one on the Settings page or set TMDB_API_KEY."
        )

    # Determine range of pages to fetch
    if page is None:
        start_page = get_tmdb_page_cursor() + 1
    else:
        start_page = max(1, int(page))

    num_pages = max(1, int(pages))
    end_page = start_page + num_pages - 1

    items = []
    seen_ids = set()
    seen_titles = set()
    last_successful_page = start_page - 1

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

        last_successful_page = p

        for movie in results:
            m_id = str(movie.get("id")) if movie.get("id") else ""
            raw_title = (movie.get("title") or "").strip()
            norm_title = raw_title.lower()

            if (m_id and m_id in seen_ids) or (norm_title and norm_title in seen_titles):
                continue

            if m_id:
                seen_ids.add(m_id)
            if norm_title:
                seen_titles.add(norm_title)

            # Map TMDB genre IDs to human-readable names
            genre_ids = movie.get("genre_ids", [])
            genre_names = [TMDB_GENRES[gid] for gid in genre_ids if gid in TMDB_GENRES]
            genre_tags = ",".join(genre_names)

            items.append(
                {
                    "type": "movie",
                    "external_id": m_id or None,
                    "title": raw_title,
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

    actual_end_page = max(start_page, last_successful_page)
    if auto_advance and actual_end_page >= start_page:
        advance_tmdb_page_cursor(actual_end_page)

    return TMDBFetchResult(items, start_page, actual_end_page)


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
