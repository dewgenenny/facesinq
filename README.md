# FaceSinq

FaceSinq is a Slack bot designed to help team members learn each other's names and faces through interactive quizzes. It syncs user data from Slack, encrypts sensitive information (names, profile images), and provides a gamified experience with leaderboards and stats.

## Features

- **Slack Integration**: Automatically syncs users from your Slack workspace (names and profile pictures).
- **Privacy First**: All user names and image URLs are encrypted in the database using Fernet encryption.
- **Interactive Quizzes**:
  - `/facesinq quiz`: Triggers a quiz where you identify a colleague's face.
  - Multiple choice buttons.
  - "Next Quiz" flow.
- **Opt-in Mechanism**:
  - Users must explicitly opt-in (`/facesinq opt-in`) to participate in quizzes.
  - Users can opt-out at any time (`/facesinq opt-out`).
- **Stats & Leaderboard**:
  - `/facesinq stats`: View global stats (e.g., number of opted-in users).
  - `/facesinq score`: View your personal score.
  - `/facesinq leaderboard`: View the top scorers in the channel.
- **Admin Tools**:
  - `/facesinq sync-users`: Manually trigger a user sync (rate-limited).
  - `/facesinq reset-quiz @user`: Reset a user's quiz session (Admin only).

## Deployment

The application is containerized and ready for deployment on Kubernetes via ArgoCD.

### Prerequisites

- **Kubernetes Cluster**
- **ArgoCD** installed in the cluster.
- **PostgreSQL Database** (Optional but recommended for production. Default is SQLite).
- **Slack App Credentials**:
  - Bot Token (`xoxb-...`)
  - Signing Secret
  - Client ID & Secret
  - Redirect URI

### 1. Build and Push Docker Image

The Docker image is automatically built and pushed to GitHub Container Registry (GHCR) via GitHub Actions on every push to `main`.

**Image Path:** `ghcr.io/<your-github-username>/facesinq:latest`

> [!NOTE]
> Ensure you update the `image` field in `k8s/deployment.yaml` to match this path.

To trigger a manual build, simply push a commit to the `master` branch.

### 2. Configure Secrets

You need to create a Kubernetes Secret named `facesinq-secrets` containing your sensitive configuration.

A template is provided in `k8s/secrets-template.yaml`.

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: facesinq-secrets
type: Opaque
stringData:
  DATABASE_URL: "postgresql://user:password@host:5432/dbname"
  SLACK_BOT_TOKEN: "xoxb-..."
  SLACK_SIGNING_SECRET: "..."
  CLIENT_ID: "..."
  CLIENT_SECRET: "..."
  REDIRECT_URI: "https://your-domain.com/slack/oauth_redirect"
  # Generate key with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ENCRYPTION_KEY: "..." 
```

### Generating an Encryption Key

You must generate a valid Fernet key for the `ENCRYPTION_KEY` variable. You can do this using Python:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Alternatively, you can run the included helper script:
```bash
python create_encryption_key.py
```


Apply the secret:
```bash
kubectl apply -f k8s/secrets-template.yaml
```

### 3. Deploy Application

You can deploy directly with `kubectl` or use the provided ArgoCD Application manifest.

**Using ArgoCD:**
```bash
kubectl apply -f k8s/argocd-app.yaml
```
*Note: You may need to update the `repoURL` in `k8s/argocd-app.yaml` to point to your repository.*

**Using kubectl directly:**
```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `PORT` | Port the app runs on | No | `3000` |
| `DATABASE_URL` | Database connection string. Supports `postgres://` or `sqlite://` | No | `sqlite:///facesinq.db` |
| `SLACK_BOT_TOKEN` | Slack Bot User OAuth Token | Yes | - |
| `SLACK_SIGNING_SECRET` | Slack Signing Secret for verifying requests | Yes | - |
| `CLIENT_ID` | Slack App Client ID | Yes | - |
| `CLIENT_SECRET` | Slack App Client Secret | Yes | - |
| `REDIRECT_URI` | OAuth Redirect URI | Yes | - |
| `ENCRYPTION_KEY` | Fernet key for encrypting data | Yes | - |

## Local Development

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate # or venv\Scripts\activate on Windows
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set environment variables (create a `.env` file or export them).
4. Run the app:
   ```bash
   python app.py
   ```
