import os
from unittest.mock import patch

from cryptography.fernet import Fernet

# ── env vars must be set before any app module is imported ──────────────────
_TEST_KEY = Fernet.generate_key().decode()
os.environ.setdefault("DATABASE_URL", "sqlite:///tests/test_facesinq.db")
# Use setdefault for most vars but explicitly handle ENCRYPTION_KEY: if it is
# absent or empty (e.g. GitHub Actions resolves a missing secret to ""), replace
# it with a freshly generated Fernet key so models.py doesn't raise on import.
if not os.environ.get("ENCRYPTION_KEY"):
    os.environ["ENCRYPTION_KEY"] = _TEST_KEY
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test-token")
os.environ.setdefault("SLACK_SIGNING_SECRET", "a" * 32)
os.environ.setdefault("CLIENT_ID", "test_client_id")
os.environ.setdefault("CLIENT_SECRET", "test_client_secret")
os.environ.setdefault("REDIRECT_URI", "http://localhost/oauth")

# Patch scheduler start and the initial Slack user-sync that run at app import time
_sched_patcher = patch("apscheduler.schedulers.background.BackgroundScheduler.start")
_sched_patcher.start()
_sync_patcher = patch("utils.fetch_and_store_users_for_all_workspaces")
_sync_patcher.start()

import pytest  # noqa: E402 — must come after env setup

# ── DB fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables once for the test session."""
    from db import engine
    from models import Base

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    # Remove the test DB file
    db_path = "tests/test_facesinq.db"
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture(autouse=True)
def clean_db():
    """Truncate all tables between tests."""
    yield
    from db import Session
    from models import QuizSession, Score, ScoreHistory, User, Workspace

    with Session() as session:
        session.query(ScoreHistory).delete()
        session.query(QuizSession).delete()
        session.query(Score).delete()
        session.query(User).delete()
        session.query(Workspace).delete()
        session.commit()


# ── helpers ──────────────────────────────────────────────────────────────────


@pytest.fixture
def make_user():
    """Factory: create a User row and return it."""
    from database_helpers import add_or_update_user

    def _make(user_id="U001", name="Alice", image="http://example.com/alice.jpg", team_id="T001"):
        add_or_update_user(user_id, name, image, team_id)
        from database_helpers import get_user

        return get_user(user_id)

    return _make


@pytest.fixture
def make_workspace():
    """Factory: create a Workspace row and return it."""
    from database_helpers import add_workspace

    def _make(team_id="T001", name="Test Workspace", token="xoxb-workspace-token"):
        add_workspace(team_id, name, token)
        from db import Session
        from models import Workspace

        with Session() as s:
            return s.query(Workspace).filter_by(id=team_id).one()

    return _make


@pytest.fixture
def flask_client():
    """Flask test client with Slack signature verification bypassed."""
    # app.py imports verify_slack_signature into its own namespace via
    # `from slack_client import verify_slack_signature`, so we must patch
    # the name in app's namespace, not in slack_client's.
    with patch("app.verify_slack_signature", return_value=True):
        from app import app

        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client
