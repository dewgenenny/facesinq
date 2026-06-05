# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

FaceSinq is a Slack bot (Flask/Python) that runs a colleague-recognition quiz game. Users are shown a photo and must guess the colleague's name. It supports multiple Slack workspaces, OAuth installation, difficulty modes, scoring, streaks, and leaderboards.

## Commands

### Local Development
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py                        # Runs on port 3000 by default
```

### Database Migrations
```bash
alembic upgrade head                 # Apply all pending migrations
alembic revision --autogenerate -m "description"  # Generate new migration
```

### Docker
```bash
docker build -t facesinq:latest .
docker run -p 3000:3000 --env-file .env facesinq:latest
```

### Generate Encryption Key
```bash
python create_encryption_key.py
```

## Architecture

### Request Flow
Slack sends events/interactions to Flask endpoints in `app.py`. The app verifies the Slack signature, routes to the appropriate handler, and responds. All Slack API calls go through `slack_client.py`, which resolves the correct per-workspace bot token from the encrypted `workspaces` table.

### Key Files
- **`app.py`** — Flask app, all HTTP endpoints (OAuth, Slack events, slash commands, block actions, interactivity)
- **`game_manager.py`** — Quiz session lifecycle: generating questions, sending to Slack, scoring answers
- **`models.py`** — SQLAlchemy ORM: `User`, `Score`, `QuizSession`, `ScoreHistory`, `Workspace`
- **`db.py`** — Engine and session factory; call `get_db_session()` for a context-managed session
- **`database_helpers.py`** — All CRUD operations; `app.py` and `game_manager.py` call these, not the ORM directly
- **`slack_client.py`** — Wraps Slack SDK; handles OAuth and per-workspace client resolution
- **`utils.py`** — Slack user-list fetching, data parsing, user sync to DB
- **`app_home.py`** — Builds the Slack App Home tab (Block Kit JSON)
- **`leaderboard.py`** — Leaderboard ranking logic and Block Kit rendering
- **`image_utils.py`** — Generates 2×2 grid images for hard-mode quizzes (Pillow)

### Multi-Workspace Support
Each Slack workspace that installs the app gets a row in the `workspaces` table with an encrypted bot token. All queries are scoped by `team_id`. `slack_client.py` decrypts and uses the correct token per request.

### Encryption
Sensitive data (user display names, profile images, access tokens) is encrypted at rest using Fernet symmetric encryption. The key is loaded from the `ENCRYPTION_KEY` environment variable.

### Database
- Default: SQLite at `/data/facesinq.db` (persistent via Kubernetes PVC)
- Production option: PostgreSQL via `DATABASE_URL`
- Schema migrations managed with Alembic (`alembic/versions/`)

## Environment Variables

| Variable | Purpose |
|---|---|
| `SLACK_BOT_TOKEN` | Bot OAuth token |
| `SLACK_SIGNING_SECRET` | Verifies incoming Slack requests |
| `CLIENT_ID` / `CLIENT_SECRET` | OAuth app credentials |
| `REDIRECT_URI` | OAuth callback URL |
| `ENCRYPTION_KEY` | Fernet key for encrypting stored data |
| `DATABASE_URL` | SQLAlchemy DB URL (defaults to SQLite) |
| `PORT` | Server port (default: 3000) |

## Deployment

CI/CD: pushing to `master` triggers GitHub Actions (`.github/workflows/docker-publish.yml`) which builds the Docker image, pushes to GHCR (`ghcr.io/dewgenenny/facesinq:sha-<hash>`), and updates `k8s/deployment.yaml` with the new image tag. ArgoCD then syncs the cluster.

Kubernetes resources are in `k8s/`: `deployment.yaml`, `service.yaml` (NodePort 80→3000), `pvc.yaml` (1Gi for SQLite), `argocd-app.yaml`.

Secrets are stored in a Kubernetes Secret named `facesinq-secrets` — see README for the template.
