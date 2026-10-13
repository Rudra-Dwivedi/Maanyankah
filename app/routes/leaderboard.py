from flask import Blueprint, render_template, g

from app.db import get_db
from app.services.gamification import get_community_leaderboard, get_weekly_challenges, get_user_badges

bp = Blueprint("leaderboard", __name__, url_prefix="/leaderboard")


@bp.route("/")
def index():
    """Community leaderboards, top reviewers/curators, and weekly challenges."""
    db = get_db()
    data = get_community_leaderboard(db, limit=15)
    challenges = get_weekly_challenges(db, g.user["id"] if g.user else None)

    # Attach badge tiers to leaderboard users
    for category in ("top_reviewers", "top_curators", "most_appreciated"):
        for user_entry in data.get(category, []):
            badges = get_user_badges(db, user_entry["id"])
            user_entry["tier"] = badges.get("tier")
            user_entry["milestones"] = badges.get("milestones", [])

    return render_template(
        "leaderboard.html",
        leaderboard=data,
        challenges=challenges,
    )
