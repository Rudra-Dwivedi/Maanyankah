import re
import urllib.parse
from flask import url_for

# Curated high-fidelity YouTube video keys for catalog items across movies, music, and sports
DEFAULT_ITEM_VIDEOS = {
    # 🎬 Movies (Official Cinematic Trailers)
    "inception": "YoHD9XEInc0",
    "the dark knight": "EXeTwQWrcwY",
    "interstellar": "zSWdZVtXT7E",
    "la la land": "5xH0R_uie1U",
    "parasite": "0pdqf4P9MB8",
    "pulp fiction": "1Fg5iWmQjwk",
    "the grand budapest hotel": "s7EdQ4FqbhY",
    "whiplash": "7d_jQycdQGo",

    # 🎵 Songs (Official Music Videos & Live Performances)
    "blinding lights": "4NRXx6U8ABQ",
    "starboy": "34Na4j8AVgA",
    "humble.": "tvTRZJ-4EyI",
    "humble": "tvTRZJ-4EyI",
    "lose yourself": "_Yhyp-_hX2s",
    "bohemian rhapsody": "fJ9rUzIMcZQ",
    "hotel california": "09839DpTctU",
    "as it was": "H5v3kku4y6Q",
    "levitating": "TUVcZfQe-Kw",
    "get lucky": "5NV6Rdv1a3I",

    # 🏆 Sports (Iconic Matches, Thrilling Highlights & Turning Points)
    "mumbai indians": "9lO_VfFfW9E",
    "real madrid": "qC50WbA-u3o",
    "los angeles lakers": "r2-901h1q7E",
    "chennai super kings": "w0_LgqD1YtE",
    "manchester united": "h-w3f2Q9WqY",
}


def parse_video_source(url_or_key):
    """
    Analyzes any video source (YouTube link/id, Vimeo, direct MP4/WEBM, uploaded file)
    and returns a structured dict:
      {
        'video_type': 'youtube' | 'vimeo' | 'html5' | 'embed',
        'raw_url': url_or_key,
        'embed_url': url,
        'youtube_id': id or None,
        'vimeo_id': id or None,
        'thumbnail_url': url or None
      }
    """
    if not url_or_key:
        return {
            "video_type": "youtube",
            "raw_url": "",
            "embed_url": "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?enablejsapi=1&rel=0",
            "youtube_id": "dQw4w9WgXcQ",
            "vimeo_id": None,
            "thumbnail_url": None,
        }

    raw = str(url_or_key).strip()

    # 1. Local uploaded video file
    if raw.startswith("/static/uploads/") or raw.endswith((".mp4", ".webm", ".ogg", ".mov")):
        return {
            "video_type": "html5",
            "raw_url": raw,
            "embed_url": raw,
            "youtube_id": None,
            "vimeo_id": None,
            "thumbnail_url": None,
        }

    # 2. YouTube detection
    # Formats: youtube.com/watch?v=XYZ, youtu.be/XYZ, youtube.com/embed/XYZ, or pure 11-char key
    yt_regexes = [
        r"(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})",
        r"(?:https?:\/\/)?(?:www\.)?youtu\.be\/([a-zA-Z0-9_-]{11})",
        r"(?:https?:\/\/)?(?:www\.)?youtube(?:-nocookie)?\.com\/embed\/([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for pattern in yt_regexes:
        match = re.search(pattern, raw)
        if match:
            yt_id = match.group(1)
            return {
                "video_type": "youtube",
                "raw_url": f"https://www.youtube.com/watch?v={yt_id}",
                "embed_url": f"https://www.youtube-nocookie.com/embed/{yt_id}?enablejsapi=1&rel=0&playsinline=1&modestbranding=1",
                "youtube_id": yt_id,
                "vimeo_id": None,
                "thumbnail_url": f"https://img.youtube.com/vi/{yt_id}/hqdefault.jpg",
            }

    # 3. Vimeo detection
    vimeo_match = re.search(r"(?:https?:\/\/)?(?:www\.)?vimeo\.com\/(?:channels\/(?:\w+\/)?|groups\/([^\/]*)\/videos\/|album\/(\d+)\/video\/|)(\d+)", raw)
    if vimeo_match:
        vimeo_id = vimeo_match.group(3)
        return {
            "video_type": "vimeo",
            "raw_url": f"https://vimeo.com/{vimeo_id}",
            "embed_url": f"https://player.vimeo.com/video/{vimeo_id}?badge=0&autopause=0&player_id=0&app_id=58479",
            "youtube_id": None,
            "vimeo_id": vimeo_id,
            "thumbnail_url": None,
        }

    # 4. Fallback embed / direct URL
    return {
        "video_type": "embed",
        "raw_url": raw,
        "embed_url": raw,
        "youtube_id": None,
        "vimeo_id": None,
        "thumbnail_url": None,
    }


def resolve_item_video(item_dict, db=None):
    """
    Finds the best video stream or trailer for a catalog item (movie, song, or sports team).
    Returns parsed video info dict.
    """
    if not item_dict:
        return parse_video_source("YoHD9XEInc0")

    title = item_dict.get("title", "")
    clean_title = title.split("—")[0].strip().lower()

    # 1. Check curated key map
    if clean_title in DEFAULT_ITEM_VIDEOS:
        return parse_video_source(DEFAULT_ITEM_VIDEOS[clean_title])

    for k, v in DEFAULT_ITEM_VIDEOS.items():
        if k in clean_title or clean_title in k:
            return parse_video_source(v)

    # 2. Check metadata
    meta = item_dict.get("metadata") or {}
    if isinstance(meta, str):
        import json
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}

    if meta.get("video_url"):
        return parse_video_source(meta["video_url"])
    if meta.get("trailer_key"):
        return parse_video_source(meta["trailer_key"])

    # 3. Fallback for movie items
    if item_dict.get("type") == "movie":
        from app.services.movie_agent import resolve_movie_trailer
        trailer = resolve_movie_trailer(item_dict, db=db)
        if trailer and trailer.get("trailer_key"):
            return parse_video_source(trailer["trailer_key"])

    # Safe fallback
    return parse_video_source("YoHD9XEInc0")
