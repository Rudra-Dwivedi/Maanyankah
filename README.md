# मान्यांकः (Maanyankah)

A social cinema and taste platform that matches people by taste across movies, music, and sports, and helps groups decide what to watch or listen to together using a collaborative filtering recommendation engine and AI agent (चित्राङ्कः).

---

## Features

- **Personalized Recommendations & Social Matching**:
  - Item rating system ($1-5$ stars) across movies, music tracks, and sports teams.
  - Cosine similarity matching (`/recommend/people`) to discover members with identical tastes.
  - Social graph with follow/unfollow capabilities and public user profiles (`/recommend/user/<username>`).

- **Group Pick Engine**:
  - Multi-user joint recommendation aggregation (`/recommend/group`).
  - Supports configurable strategies: **Average** (maximum group satisfaction) and **Least Misery** (minimizes worst-case disappointment).
  - Clean member picker filtered strictly to community members you actively follow.

- **AI Cinema Agent (चित्राङ्कः / Chitrankah)**:
  - Floating and full-screen studio assistant (`/agent/`).
  - Analyzes real community rating distributions ($1★ \to 5★$ curves) and viewer sentiment.
  - Conversational recommendations and film trivia.

- **Curated Collections (Playlists / Watchlists)**:
  - Create and share themed collections (`/collections/`) mixing movies and songs (e.g., "Late Night Sci-Fi", "Synthwave & Cinema").
  - 4-thumbnail artwork preview mosaic, community explore hub, and private collection support.
  - Interactive 1-click "+ Collection" modal on browse item cards to toggle items or create collections inline.
  - Featured on public user profiles (`/recommend/user/<username>`).

- **Genre-Wise Dynamic Filtering**:
  - Browse movies and music filtered by genre tags (`/items/?type=movie&genre=sci-fi`, `/items/?type=song&genre=pop`).
  - Interactive genre pill bar with live item count badges.
  - Clickable genre tag chips on item cards for instant deep filtering.

- **High-Definition Media Resolution**:
  - Automated artwork fetching: 1000px+ official theatrical studio posters (IMDb CDN), $1000 \times 1000$ Apple Music square covers, and transparent sports crests (TheSportsDB).
  - High-DPI / Retina anti-aliasing and optimized aspect ratios.

- **Dynamic User Profile & Photos**:
  - In-place dynamic modal for profile photo (DP) uploads and bio editing with instant preview.
  - Asynchronous AJAX updates without full page reloads.

- **Community Feed & Sentiment Analysis**:
  - Live feed (`/feed/`) with NLP polarity scoring and sentiment classification.
  - Admin announcements pinned to the top of the feed.

- **Admin Governance & Moderation**:
  - Dedicated administrative portal (`/admin/dashboard`) backed by Role-Based Access Control (RBAC).
  - **User Directory**: Search, inspect detailed activity profiles, suspend/reactivate accounts, and manage admin roles.
  - **Moderation**: Filter and purge abusive posts and spam ratings.
  - **Catalog Management**: Add, delete, and automatically resolve high-definition artwork for movies, songs, and teams.
  - **Activity Stream**: Real-time event log tracking registrations, posts, and ratings.

---

## Quick Start

### 1. Clone & Install Dependencies

```bash
git clone https://github.com/Rudra-Dwivedi/maanyankah.git
cd maanyankah
pip install -r requirements.txt
```

### 2. Run the Application

```bash
python run.py
```
*The SQLite database schema initializes automatically on first startup.*
Open **http://127.0.0.1:5000** in your browser. You can create accounts anytime via **Join free** (`/auth/register`).

### 3. Create an Administrator Account

```bash
python create_admin.py
```
*Follow the interactive prompts (or pass `--username` and `--password`) to create an administrator account for access to the Admin Portal (`/admin/login`).*

---

## Deploy to Railway

Deploying मान्यांकः (Maanyankah) live to [Railway](https://railway.app) takes less than 2 minutes:

1. **Push your code to GitHub**:
   Ensure your latest changes are pushed to your repository: `git push origin main`.

2. **Create a New Project on Railway**:
   - Go to [railway.app](https://railway.app) and log in with your GitHub account.
   - Click **+ New Project** $\rightarrow$ **Deploy from GitHub repo**.
   - Choose your repository: `Rudra-Dwivedi/maanyankah`.
   - Railway will automatically detect Python, install dependencies via `requirements.txt`, and launch the production Gunicorn server via `Procfile` and `railway.json`.

3. **Configure Environment Variables** *(Recommended)*:
   In your Railway project dashboard, click on your service $\rightarrow$ **Variables** tab:
   - `SECRET_KEY`: Any secret random string for secure session encryption.
   - `ADMIN_USERNAME`: Your chosen admin username (e.g. `admin`).
   - `ADMIN_PASSWORD`: Your chosen admin password (e.g. `admin123`).
   *On first launch, Maanyankah will automatically provision your admin account and seed starter catalog items with HD artwork!*

4. **Generate Public URL**:
   - In your Railway service dashboard $\rightarrow$ **Settings** $\rightarrow$ **Networking**, click **Generate Domain**.
   - Your live website URL is ready to share!

---

## Project Structure

```
maanyankah/
├── app/
│   ├── __init__.py          # Flask application factory
│   ├── db.py                # Database connection & schema migrations
│   ├── schema.sql           # SQLite schema definitions
│   ├── auth_utils.py        # RBAC decorators (login_required, admin_required)
│   ├── routes/
│   │   ├── auth.py          # Registration, login, logout, and profile photo settings
│   │   ├── admin.py         # Admin dashboard, users, posts, ratings, and catalog
│   │   ├── items.py         # Browse catalog & rate items
│   │   ├── recommend.py     # Discover similar people, public profiles, and group picks
│   │   ├── feed.py          # Community feed and pinned announcements
│   │   └── settings.py      # API key configurations
│   ├── services/
│   │   ├── recommender.py   # Taste vectors, cosine similarity, group aggregation
│   │   ├── sentiment.py     # Sentiment analysis scorer
│   │   ├── image_fetcher.py # HD artwork discovery service (IMDb, iTunes, TheSportsDB)
│   │   ├── item_media.py    # Media resolution helper
│   │   ├── settings_store.py# API key storage
│   │   ├── tmdb_client.py   # TMDB client
│   │   ├── spotify_client.py# Spotify search client
│   │   └── sports_client.py # Sports API client
│   ├── templates/           # Jinja2 HTML templates
│   └── static/
│       ├── style.css        # Responsive CSS theme
│       └── avatars/         # Uploaded user profile photos
├── config.py                # App configuration
├── create_admin.py          # CLI admin creation tool
├── Procfile                 # Production WSGI process definition for Railway
├── railway.json             # Railway Nixpacks deployment configuration
├── runtime.txt              # Python runtime version
├── requirements.txt         # Python package dependencies (including Gunicorn)
├── run.py                   # Server runner with dynamic port binding
└── README.md                # Documentation
```

---

## License

MIT License.
