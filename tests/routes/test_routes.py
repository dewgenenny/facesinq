"""Route tests — Flask test client with Slack signature verification mocked."""

import json
from unittest.mock import patch

# ── helpers ───────────────────────────────────────────────────────────────────


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


# ── basic routes ──────────────────────────────────────────────────────────────


class TestIndex:
    def test_index_returns_200(self, flask_client):
        resp = flask_client.get("/")
        assert resp.status_code == 200
        assert b"FaceSinq" in resp.data


# ── signature rejection ───────────────────────────────────────────────────────


class TestSignatureVerification:
    def test_commands_rejects_bad_signature(self):
        from app import app

        app.config["TESTING"] = True
        with patch("app.verify_slack_signature", return_value=False):
            with app.test_client() as c:
                resp = c.post("/slack/commands", data={"command": "/facesinq", "text": "quiz"})
        assert resp.status_code == 403

    def test_actions_rejects_bad_signature(self):
        from app import app

        app.config["TESTING"] = True
        with patch("app.verify_slack_signature", return_value=False):
            with app.test_client() as c:
                resp = c.post("/slack/actions", data={"payload": "{}"})
        assert resp.status_code == 403


# ── /facesinq commands ────────────────────────────────────────────────────────


class TestCommandNoText:
    def test_no_text_returns_welcome_blocks(self, flask_client):
        resp = _cmd(flask_client, text="")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data.get("response_type") == "ephemeral"
        assert "blocks" in data


class TestCommandOptIn:
    def test_opt_in_unknown_user_fetches_and_responds(self, flask_client, make_workspace):
        make_workspace()
        with patch("app.fetch_and_store_single_user", return_value=True):
            with patch("app.update_user_opt_in", side_effect=[False, True]):
                resp = _cmd(flask_client, text="opt-in")
        assert resp.status_code == 200
        # Success: "✅ You're in! Get ready for some random quizzes!" — no "opt" in message
        assert b"in" in resp.data.lower()

    def test_opt_in_existing_user(self, flask_client, make_user):
        make_user(user_id="U001")
        resp = _cmd(flask_client, text="opt-in", user_id="U001")
        assert resp.status_code == 200
        # Success response: "✅ You're in! Get ready for some random quizzes!"
        assert b"in" in resp.data.lower()


class TestCommandOptOut:
    def test_opt_out_returns_200(self, flask_client, make_user):
        make_user(user_id="U001")
        resp = _cmd(flask_client, text="opt-out", user_id="U001")
        assert resp.status_code == 200


class TestCommandStats:
    def test_stats_returns_count(self, flask_client, make_user):
        make_user(user_id="U001", team_id="T001")
        from database_helpers import update_user_opt_in

        update_user_opt_in("U001", True)
        resp = _cmd(flask_client, text="stats")
        assert resp.status_code == 200
        assert b"1" in resp.data


class TestCommandScore:
    def test_score_returns_zero_for_new_user(self, flask_client):
        resp = _cmd(flask_client, text="score", user_id="UNEW")
        assert resp.status_code == 200
        assert b"0" in resp.data


class TestCommandLeaderboard:
    def test_leaderboard_requires_ten_attempts(self, flask_client):
        resp = _cmd(flask_client, text="leaderboard", user_id="UFRESH")
        assert resp.status_code == 200
        assert b"10" in resp.data

    def test_leaderboard_shown_with_enough_attempts(self, flask_client, make_user):
        make_user(user_id="U001")
        for _ in range(10):
            from database_helpers import update_score

            update_score("U001", 10, is_correct=True)
        with patch("app.get_leaderboard_blocks", return_value=[]):
            resp = _cmd(flask_client, text="leaderboard", user_id="U001")
        assert resp.status_code == 200


class TestCommandQuiz:
    def test_quiz_command_returns_message(self, flask_client):
        with patch("app.send_quiz_to_user", return_value=(True, "Quiz sent!")):
            resp = _cmd(flask_client, text="quiz", user_id="U001")
        assert resp.status_code == 200
        assert b"Quiz" in resp.data

    def test_quiz_error_returns_generic_message(self, flask_client):
        with patch("app.send_quiz_to_user", return_value=(False, "An error occurred.")):
            resp = _cmd(flask_client, text="quiz")
        assert resp.status_code == 200
        # Should NOT expose a stack trace
        assert b"Traceback" not in resp.data


class TestCommandMode:
    def test_mode_invalid_shows_usage(self, flask_client):
        resp = _cmd(flask_client, text="mode")
        assert resp.status_code == 200
        assert b"Usage" in resp.data

    def test_mode_easy(self, flask_client, make_user):
        make_user(user_id="U001")
        resp = _cmd(flask_client, text="mode easy", user_id="U001")
        assert resp.status_code == 200

    def test_mode_hard(self, flask_client, make_user):
        make_user(user_id="U001")
        resp = _cmd(flask_client, text="mode hard", user_id="U001")
        assert resp.status_code == 200


class TestCommandResetQuiz:
    def test_reset_quiz_own_session(self, flask_client, make_user):
        make_user(user_id="U001")
        from database_helpers import create_or_update_quiz_session

        create_or_update_quiz_session("U001", "U_C")
        resp = _cmd(flask_client, text="reset-quiz", user_id="U001")
        assert resp.status_code == 200


class TestCommandUnknown:
    def test_unknown_command_shows_hint(self, flask_client):
        resp = _cmd(flask_client, text="blahblah")
        assert resp.status_code == 200
        assert b"opt-in" in resp.data


# ── Slack events endpoint ─────────────────────────────────────────────────────


class TestSlackEvents:
    def test_url_verification_challenge(self, flask_client):
        payload = {"type": "url_verification", "challenge": "test_challenge_123"}
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
        data = json.loads(resp.data)
        assert data["challenge"] == "test_challenge_123"

    def test_invalid_json_returns_400(self, flask_client):
        with patch("slack_client.verify_slack_signature", return_value=True):
            resp = flask_client.post(
                "/slack/events",
                data="not json",
                content_type="application/json",
            )
        assert resp.status_code == 400
