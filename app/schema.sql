-- मन्यांकः (Manyankah) database schema

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    is_active INTEGER NOT NULL DEFAULT 1,
    avatar_url TEXT,
    bio TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Unified table for movies, songs, and sports teams/events.
-- "type" is one of: 'movie', 'song', 'team'
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK (type IN ('movie', 'song', 'team')),
    external_id TEXT,              -- id from TMDB / Spotify / sports API
    title TEXT NOT NULL,
    genre_tags TEXT,               -- comma-separated tags, e.g. "action,thriller"
    metadata TEXT,                 -- JSON blob: poster url, artist, league, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Unique indexes to prevent duplicate movies, songs, or teams in catalog
CREATE UNIQUE INDEX IF NOT EXISTS idx_items_unique_type_title ON items(type, LOWER(TRIM(title)));
CREATE UNIQUE INDEX IF NOT EXISTS idx_items_unique_type_extid ON items(type, external_id) WHERE external_id IS NOT NULL AND external_id != '';


CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    item_id INTEGER NOT NULL REFERENCES items(id),
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, item_id)
);

CREATE TABLE IF NOT EXISTS follows (
    follower_id INTEGER NOT NULL REFERENCES users(id),
    followed_id INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (follower_id, followed_id)
);

CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS group_members (
    group_id INTEGER NOT NULL REFERENCES groups(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    PRIMARY KEY (group_id, user_id)
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    item_id INTEGER REFERENCES items(id),
    content TEXT NOT NULL,
    sentiment_score REAL,
    is_pinned INTEGER NOT NULL DEFAULT 0,
    is_spoiler INTEGER NOT NULL DEFAULT 0,
    spoiler_warning TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Simple key/value store for API keys entered through the Settings page,
-- so they can be set from the UI instead of environment variables.
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- User-curated collections of movies and songs (playlists/lists)
CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    is_public INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS collection_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    note TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(collection_id, item_id)
);

-- Quick emoji reactions on community reviews/posts (🔥, ❤️, 👏, 🤯, 😡)
CREATE TABLE IF NOT EXISTS post_reactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    reaction TEXT NOT NULL CHECK (reaction IN ('fire', 'love', 'insightful', 'mindblown', 'disagree')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, post_id)
);

-- Bookmarks / follows on curated collections
CREATE TABLE IF NOT EXISTS collection_bookmarks (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(user_id, collection_id)
);

-- Community comments / discussions on collections
CREATE TABLE IF NOT EXISTS collection_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 🎬 Movies: Multi-criteria aspect ratings (Storyline, Acting, Direction, Cinematography, Music)
CREATE TABLE IF NOT EXISTS movie_aspect_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    storyline INTEGER CHECK (storyline BETWEEN 1 AND 5),
    acting INTEGER CHECK (acting BETWEEN 1 AND 5),
    direction INTEGER CHECK (direction BETWEEN 1 AND 5),
    cinematography INTEGER CHECK (cinematography BETWEEN 1 AND 5),
    music INTEGER CHECK (music BETWEEN 1 AND 5),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, item_id)
);

-- Community mood tags (e.g., "chill", "intense", "family-friendly", "mind-bending", "dark", "heartfelt")
CREATE TABLE IF NOT EXISTS item_mood_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mood TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(item_id, user_id, mood)
);

-- 🎵 Songs: Emotion-based ratings, replay value, and lyrics vs. music split
CREATE TABLE IF NOT EXISTS song_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    emotion TEXT CHECK (emotion IN ('happy', 'sad', 'energetic', 'chill', 'melancholic', 'euphoric', 'romantic')),
    replay_value INTEGER CHECK (replay_value BETWEEN 1 AND 5), -- 1=Rarely, 3=Occasional, 5=Daily on Repeat 🔥
    lyrics_score INTEGER CHECK (lyrics_score BETWEEN 1 AND 5),
    music_score INTEGER CHECK (music_score BETWEEN 1 AND 5),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, item_id)
);

-- Quick emoji reactions on catalog items/songs (🔥, ❤️, 🎶, ⚡, 🎧)
CREATE TABLE IF NOT EXISTS item_quick_reactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    reaction TEXT NOT NULL CHECK (reaction IN ('fire', 'love', 'vibe', 'energetic', 'masterpiece')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, item_id, reaction)
);

-- 🏆 Sports: Match excitement index (Thrill, Competitiveness, Memorable Moments)
CREATE TABLE IF NOT EXISTS sports_match_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    thrill_level INTEGER CHECK (thrill_level BETWEEN 1 AND 5),
    competitiveness INTEGER CHECK (competitiveness BETWEEN 1 AND 5),
    memorable_moments INTEGER CHECK (memorable_moments BETWEEN 1 AND 5),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, item_id)
);

-- 🏆 Sports: Player performance ratings & MVP nominations
CREATE TABLE IF NOT EXISTS sports_player_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    player_name TEXT NOT NULL,
    rating INTEGER CHECK (rating BETWEEN 1 AND 10),
    is_mvp INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, item_id, player_name)
);

-- 🏆 Sports: Match outcome predictions & fan credibility points
CREATE TABLE IF NOT EXISTS sports_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    predicted_outcome TEXT NOT NULL, -- e.g. "Home Win", "Away Win", "Draw"
    confidence_points INTEGER NOT NULL DEFAULT 10,
    actual_outcome TEXT,             -- Filled upon match resolution
    is_correct INTEGER,              -- NULL=pending, 1=correct, 0=incorrect
    points_awarded INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, item_id)
);

-- 🏆 Sports: Highlight voting ("Best Play", "Turning Point", "Clutch Moment")
CREATE TABLE IF NOT EXISTS sports_highlight_votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    highlight_type TEXT NOT NULL CHECK (highlight_type IN ('best_play', 'turning_point', 'clutch_moment', 'mvp_performance')),
    highlight_title TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, item_id, highlight_type)
);

