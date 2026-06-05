"""Additional route tests for higher coverage."""

import json
from unittest.mock import patch

import pytest


def _cmd(client, text="", command="/facesinq", user_id="U001", team_id="T001", channel_id="C001"):
    return client.post(
        "/slack/commands",
        data={
            "command": command,
            "text": text,
            "user_id": user_id,
            "team_id": team_id,
            "channel_id": channel_id,
        },
    )


# ── begin_install / oauth_redirect ───────────────────────────────────────────


class TestBeginInstall:
    def test_begin_install_redirects_to_slack(self, flask_client):
        resp = flask_client.get("/slack/begin_install")
        assert resp.status_code == 302
        assert "slack.com/oauth/v2/authorize" in resp.headers["Location"]

    def test_begin_install_sets_state_cookie(self, flask_client):
        with flask_client.session_transaction() as pre:
            assert "oauth_state" not in pre
        flask_client.get("/slack/begin_install")
        with flask_client.session_transaction() as post:
            assert "oauth_state" in post

    def test_oauth_redirect_rejects_missing_state(self, flask_client):
        resp = flask_client.get("/slack/oauth_redirect?code=CODE123")
        assert resp.status_code == 403

    def test_oauth_redirect_rejects_wrong_state(self, flask_client):
        with flask_client.session_transaction() as sess:
            sess["oauth_state"] = "correct-state"
        resp = flask_client.get("/slack/oauth_redirect?code=CODE123&state=wrong-state")
        assert resp.status_code == 403

    def test_oauth_redirect_accepts_correct_state(self, flask_client):
        with flask_client.session_transaction() as sess:
            sess["oauth_state"] = "my-state"
        with patch(
            "app.handle_slack_oauth_redirect", return_value=(True, "Installation Successful!")
        ):
            resp = flask_client.get("/slack/oauth_redirect?code=CODE123&state=my-state")
        assert resp.status_code == 200


# ── sync-users command ────────────────────────────────────────────────────────


class TestCommandSyncUsers:
    def test_sync_users_existing_workspace(self, flask_client, make_workspace):
        make_workspace(team_id="T001")
        with patch("app.fetch_and_store_users", return_value=None):
            resp = _cmd(flask_client, text="sync-users", team_id="T001")
        assert resp.status_code == 200

    def test_sync_users_rate_limited(self, flask_client, make_workspace):
        make_workspace(team_id="T002")
        # Simulate that a sync already happened
        import time

        import app as app_module

        app_module.last_sync_times["T002"] = time.time()
        with patch("app.fetch_and_store_users", return_value=None):
            resp = _cmd(flask_client, text="sync-users", team_id="T002")
        assert resp.status_code == 200
        # The outer route always returns "Syncing users"; rate limit is enforced
        # inside handle_sync_users_command but its return value is ignored there.
        assert b"Syncing" in resp.data


# ── wipe-all-scores command ────────────────────────────────────────────────────


class TestCommandWipeAllScores:
    def test_non_admin_rejected(self, flask_client, make_user):
        make_user(user_id="U001")
        with patch("app.is_user_workspace_admin", return_value=False):
            resp = _cmd(flask_client, text="wipe-all-scores", user_id="U001")
        assert resp.status_code == 200
        assert b"permission" in resp.data.lower()

    def test_admin_triggers_wipe(self, flask_client, make_user):
        make_user(user_id="UADMIN")
        with patch("app.is_user_workspace_admin", return_value=True):
            resp = _cmd(flask_client, text="wipe-all-scores", user_id="UADMIN")
        assert resp.status_code == 200


# ── reset-score command ───────────────────────────────────────────────────────


class TestCommandResetScore:
    def test_reset_own_score(self, flask_client, make_user):
        make_user(user_id="U001")
        from database_helpers import update_score

        update_score("U001", 10, is_correct=True)
        resp = _cmd(flask_client, text="reset-score", user_id="U001")
        assert resp.status_code == 200

    def test_reset_other_user_requires_admin(self, flask_client, make_user):
        make_user(user_id="U001")
        make_user(user_id="U002")
        with patch("app.is_user_workspace_admin", return_value=False):
            resp = _cmd(flask_client, text="reset-score <@U002>", user_id="U001")
        assert resp.status_code == 200
        assert b"permission" in resp.data.lower()

    def test_admin_can_reset_other_user(self, flask_client, make_user):
        make_user(user_id="U001")
        make_user(user_id="U002")
        with patch("app.is_user_workspace_admin", return_value=True):
            resp = _cmd(flask_client, text="reset-score <@U002>", user_id="U001")
        assert resp.status_code == 200


# ── facesinq-reset-quiz admin command ────────────────────────────────────────


class TestAdminResetQuiz:
    def test_non_admin_rejected(self, flask_client, make_user):
        make_user(user_id="U001")
        with patch("app.is_user_workspace_admin", return_value=False):
            resp = _cmd(
                flask_client, text="<@U001>", command="/facesinq-reset-quiz", user_id="U001"
            )
        assert resp.status_code == 200
        assert b"permission" in resp.data.lower()

    def test_admin_resets_quiz(self, flask_client, make_user):
        make_user(user_id="U001")
        make_user(user_id="U002")
        from database_helpers import create_or_update_quiz_session

        create_or_update_quiz_session("U002", "U_C")
        with patch("app.is_user_workspace_admin", return_value=True):
            resp = _cmd(
                flask_client, text="<@U002>", command="/facesinq-reset-quiz", user_id="U001"
            )
        assert resp.status_code == 200

    def test_no_user_id_in_text(self, flask_client, make_user):
        make_user(user_id="U001")
        with patch("app.is_user_workspace_admin", return_value=True):
            resp = _cmd(
                flask_client, text="not-a-user", command="/facesinq-reset-quiz", user_id="U001"
            )
        assert resp.status_code == 200
        assert b"valid user" in resp.data.lower()


# ── slack_events endpoint ─────────────────────────────────────────────────────


class TestSlackEventsMore:
    def test_event_callback_dispatched(self, flask_client):
        payload = {
            "type": "event_callback",
            "team_id": "T001",
            "event": {"type": "team_join", "user": {}},
        }
        with patch("app.verify_slack_signature", return_value=True):
            with patch("app.handle_slack_event") as mock_event:
                resp = flask_client.post(
                    "/slack/events",
                    data=json.dumps(payload),
                    content_type="application/json",
                    headers={
                        "X-Slack-Request-Timestamp": "1234567890",
                        "X-Slack-Signature": "v0=fake",
                    },
                )
        assert resp.status_code == 200
        mock_event.assert_called_once()

    def test_events_rejects_bad_signature(self, flask_client):
        payload = {"type": "event_callback", "team_id": "T001", "event": {"type": "team_join"}}
        with patch("app.verify_slack_signature", return_value=False):
            resp = flask_client.post(
                "/slack/events",
                data=json.dumps(payload),
                content_type="application/json",
                headers={
                    "X-Slack-Request-Timestamp": "1234567890",
                    "X-Slack-Signature": "v0=bad",
                },
            )
        assert resp.status_code == 403


# ── leaderboard with mocked data ──────────────────────────────────────────────


class TestLeaderboardBlocks:
    def test_get_leaderboard_blocks_structure(self):
        from leaderboard import get_leaderboard_blocks

        empty_score_list = []
        with patch("leaderboard.get_top_scores", return_value=empty_score_list):
            with patch("leaderboard.get_top_scores_period", return_value=empty_score_list):
                blocks = get_leaderboard_blocks()
        assert isinstance(blocks, list)
        assert len(blocks) > 0
        # Should have sections for daily, weekly, all-time
        header_texts = [b["text"]["text"] for b in blocks if b.get("type") == "header"]
        assert any("Daily" in t for t in header_texts)
        assert any("Weekly" in t for t in header_texts)
        assert any("All-Time" in t for t in header_texts)

    def test_leaderboard_with_scores(self):
        from leaderboard import get_leaderboard_blocks

        sample = [("Alice", 80.0, "http://img", 100, 10, 3)]
        with patch("leaderboard.get_top_scores", return_value=sample):
            with patch("leaderboard.get_top_scores_period", return_value=sample):
                blocks = get_leaderboard_blocks()
        section_texts = [
            b["text"]["text"]
            for b in blocks
            if b.get("type") == "section" and "text" in b and isinstance(b["text"], dict)
        ]
        assert any("Alice" in t for t in section_texts)


# ── game_manager generate_quiz_data ──────────────────────────────────────────


class TestGenerateQuizData:
    def test_returns_none_when_user_not_found(self):
        from game_manager import generate_quiz_data

        result = generate_quiz_data("UNOPE", "TNOPE")
        assert result is None

    def test_returns_none_when_not_enough_colleagues(self, make_user):
        make_user(user_id="U001", team_id="T001")
        make_user(user_id="U002", team_id="T001")
        # Only 1 colleague, need 4
        from game_manager import generate_quiz_data

        result = generate_quiz_data("U001", "T001")
        assert result is None

    def test_returns_quiz_data_with_enough_colleagues(self, make_user):
        for i in range(5):
            make_user(user_id=f"U{i:03d}", name=f"Person{i}", team_id="T001")
        from game_manager import generate_quiz_data

        result = generate_quiz_data("U000", "T001")
        assert result is not None
        assert "correct_choice" in result
        assert "options" in result
        assert len(result["options"]) == 4
        assert result["difficulty"] == "easy"


# ── utils fetch_and_store_users ───────────────────────────────────────────────


class TestFetchAndStoreUsers:
    def test_skips_fetch_when_users_exist(self, make_user, make_workspace):
        make_workspace(team_id="T001")
        make_user(user_id="U001", team_id="T001")
        from utils import fetch_and_store_users

        # Should return without calling Slack
        with patch("utils.fetch_users") as mock_fetch:
            fetch_and_store_users("T001", update_existing=False)
        mock_fetch.assert_not_called()

    def test_fetches_when_update_existing_true(self, make_user, make_workspace):
        make_workspace(team_id="T001")
        make_user(user_id="U001", team_id="T001")
        fake_users = [
            {
                "id": "U001",
                "real_name": "Alice",
                "is_bot": False,
                "deleted": False,
                "profile": {"image_512": "http://img.jpg"},
            }
        ]
        from utils import fetch_and_store_users

        with patch("utils.fetch_users", return_value=fake_users):
            fetch_and_store_users("T001", update_existing=True)

    def test_raises_when_no_team_id(self):
        from utils import fetch_and_store_users

        with pytest.raises(ValueError):
            fetch_and_store_users(None)
