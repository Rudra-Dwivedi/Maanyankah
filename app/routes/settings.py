from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.db import get_db
from app.auth_utils import admin_required
from app.services.settings_store import set_setting, all_settings_masked
from app.services import tmdb_client, spotify_client, sports_client

bp = Blueprint("settings", __name__, url_prefix="/settings")


@bp.route("/", methods=["GET", "POST"])
@admin_required
def api_keys():
    if request.method == "POST":
        for field in ("tmdb_api_key", "spotify_client_id", "spotify_client_secret", "sports_api_key"):
            value = request.form.get(field, "").strip()
            if value:  # only overwrite if the person actually typed something new
                set_setting(field.upper(), value)
        flash("API keys saved.")
        return redirect(url_for("settings.api_keys"))

    db = get_db()
    movie_count = db.execute("SELECT COUNT(*) AS c FROM items WHERE type = 'movie'").fetchone()["c"]
    song_count = db.execute("SELECT COUNT(*) AS c FROM items WHERE type = 'song'").fetchone()["c"]
    team_count = db.execute("SELECT COUNT(*) AS c FROM items WHERE type = 'team'").fetchone()["c"]
    tmdb_last_page = tmdb_client.get_tmdb_page_cursor()
    tmdb_next_page = tmdb_last_page + 1

    return render_template(
        "settings.html",
        saved=all_settings_masked(),
        movie_count=movie_count,
        song_count=song_count,
        team_count=team_count,
        tmdb_last_page=tmdb_last_page,
        tmdb_next_page=tmdb_next_page,
    )


@bp.route("/fetch/movies", methods=["POST"])
@admin_required
def fetch_movies():
    try:
        fetch_mode = request.form.get("fetch_mode", "auto")
        current_cursor = tmdb_client.get_tmdb_page_cursor()

        if fetch_mode == "custom":
            start_page = request.form.get("custom_start_page", 1, type=int)
            start_page = max(1, start_page)
        else:
            start_page = current_cursor + 1

        pages_val = request.form.get("pages", "3")
        if pages_val == "custom":
            pages = request.form.get("custom_pages", 3, type=int)
        else:
            try:
                pages = int(pages_val)
            except (ValueError, TypeError):
                pages = 3
        pages = max(1, min(pages, 50))  # Allow up to 50 pages (1,000 movies) in one batch!

        db = get_db()
        result = tmdb_client.fetch_popular_movies(page=start_page, pages=pages)
        inserted, skipped = tmdb_client.save_items(db, result)

        actual_end = result.end_page if hasattr(result, "end_page") else (start_page + pages - 1)
        tmdb_client.advance_tmdb_page_cursor(actual_end)

        range_desc = f"page {start_page}" if start_page == actual_end else f"pages {start_page}–{actual_end}"
        next_page = actual_end + 1

        msg = (
            f"Successfully fetched {len(result)} movies from TMDB across {range_desc} "
            f"({inserted} new movies added"
        )
        if skipped > 0:
            msg += f", {skipped} duplicates safely skipped"
        msg += f"). Next fetch will automatically continue from page {next_page}."
        flash(msg)
    except Exception as e:
        flash(f"Couldn't fetch movies: {e}")
    return redirect(url_for("settings.api_keys"))


@bp.route("/fetch/movies/reset", methods=["POST"])
@admin_required
def reset_movies_cursor():
    tmdb_client.reset_tmdb_page_cursor()
    flash("TMDB movie fetch cursor reset to Page 1. The next fetch will start from page 1.")
    return redirect(url_for("settings.api_keys"))


@bp.route("/fetch/music", methods=["POST"])
@admin_required
def fetch_music():
    query = request.form.get("query", "").strip()
    if not query:
        flash("Type an artist, song, or genre to search for first.")
        return redirect(url_for("settings.api_keys"))
    try:
        db = get_db()
        items = spotify_client.fetch_tracks_by_search(query)
        inserted, skipped = tmdb_client.save_items(db, items)  # save_items is format-agnostic, works for any item dict
        msg = f"Loaded {inserted} new tracks matching '{query}'."
        if skipped > 0:
            msg += f" ({skipped} duplicates safely skipped)"
        flash(msg)
    except Exception as e:
        flash(f"Couldn't fetch tracks: {e}")
    return redirect(url_for("settings.api_keys"))


@bp.route("/fetch/sports", methods=["POST"])
@admin_required
def fetch_sports():
    league = request.form.get("league", "").strip()
    if not league:
        flash("Enter a league name first, e.g. 'English Premier League'.")
        return redirect(url_for("settings.api_keys"))
    try:
        db = get_db()
        items = sports_client.fetch_teams_by_league(league)
        inserted, skipped = tmdb_client.save_items(db, items)
        msg = f"Loaded {inserted} new teams from {league}."
        if skipped > 0:
            msg += f" ({skipped} duplicates safely skipped)"
        flash(msg)
    except Exception as e:
        flash(f"Couldn't fetch teams: {e}")
    return redirect(url_for("settings.api_keys"))

