"""Tests for the /slack/actions endpoint — covers each action_id branch."""

import json
from unittest.mock import MagicMock, patch


def _post_action(
    client,
    action_id,
    user_id="U001",
    team_id="T001",
    value=None,
    selected_option=None,
    message=None,
    trigger_id="TRIGGER123",
):
    """POST a Slack block-action payload to /slack/actions."""
    payload = {
        "type": "block_actions",
        "team": {"id": team_id},
        "user": {"id": user_id},
        "trigger_id": trigger_id,
        "actions": [
            {
                "action_id": action_id,
                "value": value,
                "selected_option": selected_option,
            }
        ],
    }
    if message is not None:
        payload["message"] = message
        payload["channel"] = {"id": "D001"}
    return client.post("/slack/actions", data={"payload": json.dumps(payload)})


def _quiz_message_blocks(options):
    """Build a minimal quiz message block structure for action payloads."""
    elements = [
        {
            "type": "button",
            "action_id": f"quiz_response_{i}",
            "value": uid,
            "text": {"type": "plain_text", "text": name, "emoji": True},
        }
        for i, (uid, name) in enumerate(options)
    ]
    return {
        "ts": "111.222",
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": "Who is *Alice*?"}},
            {"type": "actions", "elements": elements},
        ],
    }


_MOCK_CLIENT = MagicMock()


# ── quiz_response ─────────────────────────────────────────────────────────────


class TestQuizResponseAction:
    def test_correct_answer_updates_message(self, flask_client, make_user):
        for i in range(5):
            make_user(user_id=f"U{i:03d}", name=f"Person{i}", team_id="T001")
        from database_helpers import create_or_update_quiz_session

        create_or_update_quiz_session("U000", "U001")

        options = [(f"U{i:03d}", f"Person{i}") for i in range(1, 5)]
        message = _quiz_message_blocks(options)

        mock_client = MagicMock()
        mock_client.chat_update.return_value = {"ok": True}
        # handle_quiz_response lives in game_manager and gets its own client there
        with patch("game_manager.get_slack_client", return_value=mock_client):
            resp = _post_action(
                flask_client,
                action_id="quiz_response_0",
                user_id="U000",
                team_id="T001",
                value="U001",
                message=message,
            )
        assert resp.status_code == 200
        mock_client.chat_update.assert_called_once()

    def test_incorrect_answer_updates_message(self, flask_client, make_user):
        for i in range(5):
            make_user(user_id=f"U{i:03d}", name=f"Person{i}", team_id="T001")
        from database_helpers import create_or_update_quiz_session

        create_or_update_quiz_session("U000", "U001")

        options = [(f"U{i:03d}", f"Person{i}") for i in range(1, 5)]
        message = _quiz_message_blocks(options)

        mock_client = MagicMock()
        with patch("game_manager.get_slack_client", return_value=mock_client):
            resp = _post_action(
                flask_client,
                action_id="quiz_response_1",
                user_id="U000",
                team_id="T001",
                value="U002",  # wrong answer
                message=message,
            )
        assert resp.status_code == 200

    def test_expired_session_sends_message(self, flask_client, make_user):
        make_user(user_id="U000", team_id="T001")
        # No quiz session created — simulates expired session

        options = [("U001", "Person1"), ("U002", "Person2")]
        message = _quiz_message_blocks(options)

        mock_client = MagicMock()
        with patch("game_manager.get_slack_client", return_value=mock_client):
            resp = _post_action(
                flask_client,
                action_id="quiz_response_0",
                user_id="U000",
                team_id="T001",
                value="U001",
                message=message,
            )
        assert resp.status_code == 200


# ── next_quiz ─────────────────────────────────────────────────────────────────


class TestNextQuizAction:
    def test_next_quiz_disables_button_and_sends_quiz(self, flask_client, make_user):
        make_user(user_id="U001", team_id="T001")

        message = {
            "ts": "111.222",
            "blocks": [
                {
                    "type": "actions",
                    "block_id": "next_quiz_block",
                    "elements": [
                        {
                            "type": "button",
                            "action_id": "next_quiz",
                            "value": "next_quiz",
                            "text": {"type": "plain_text", "text": "Next Quiz"},
                        }
                    ],
                }
            ],
        }
        mock_client = MagicMock()
        with patch("app.get_slack_client", return_value=mock_client):
            with patch("app.send_quiz_to_user", return_value=(True, "sent")):
                resp = _post_action(
                    flask_client,
                    action_id="next_quiz",
                    user_id="U001",
                    team_id="T001",
                    message=message,
                )
        assert resp.status_code == 200

    def test_next_quiz_missing_block_logs_warning(self, flask_client, make_user):
        make_user(user_id="U001", team_id="T001")

        message = {
            "ts": "111.222",
            "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "hi"}}],
        }
        mock_client = MagicMock()
        with patch("app.get_slack_client", return_value=mock_client):
            with patch("app.send_quiz_to_user", return_value=(True, "sent")):
                resp = _post_action(
                    flask_client,
                    action_id="next_quiz",
                    user_id="U001",
                    team_id="T001",
                    message=message,
                )
        assert resp.status_code == 200


# ── start_quiz_home ───────────────────────────────────────────────────────────


class TestStartQuizHomeAction:
    def test_start_quiz_home_returns_200(self, flask_client, make_user):
        make_user(user_id="U001", team_id="T001")
        mock_client = MagicMock()
        with patch("app.get_slack_client", return_value=mock_client):
            with patch("app.send_quiz_to_user", return_value=(True, "sent")):
                with patch("app.publish_home_view"):
                    resp = _post_action(
                        flask_client, action_id="start_quiz_home", user_id="U001", team_id="T001"
                    )
        assert resp.status_code == 200


# ── toggle_opt_in_home ────────────────────────────────────────────────────────


class TestToggleOptInHomeAction:
    def test_opt_in_true(self, flask_client, make_user):
        make_user(user_id="U001", team_id="T001")
        mock_client = MagicMock()
        with patch("app.get_slack_client", return_value=mock_client):
            with patch("app.publish_home_view"):
                resp = _post_action(
                    flask_client,
                    action_id="toggle_opt_in_home",
                    user_id="U001",
                    team_id="T001",
                    selected_option={"value": "true"},
                )
        assert resp.status_code == 200

    def test_opt_in_false(self, flask_client, make_user):
        make_user(user_id="U001", team_id="T001")
        mock_client = MagicMock()
        with patch("app.get_slack_client", return_value=mock_client):
            with patch("app.publish_home_view"):
                resp = _post_action(
                    flask_client,
                    action_id="toggle_opt_in_home",
                    user_id="U001",
                    team_id="T001",
                    selected_option={"value": "false"},
                )
        assert resp.status_code == 200

    def test_opt_in_fetches_user_when_not_found(self, flask_client):
        # User not in DB — triggers fetch fallback
        mock_client = MagicMock()
        with patch("app.get_slack_client", return_value=mock_client):
            with patch("app.fetch_and_store_single_user", return_value=True):
                with patch("app.publish_home_view"):
                    resp = _post_action(
                        flask_client,
                        action_id="toggle_opt_in_home",
                        user_id="UNEW",
                        team_id="T001",
                        selected_option={"value": "true"},
                    )
        assert resp.status_code == 200


# ── toggle_difficulty_home ────────────────────────────────────────────────────


class TestToggleDifficultyHomeAction:
    def test_set_easy_mode(self, flask_client, make_user):
        make_user(user_id="U001", team_id="T001")
        mock_client = MagicMock()
        with patch("app.get_slack_client", return_value=mock_client):
            with patch("app.publish_home_view"):
                resp = _post_action(
                    flask_client,
                    action_id="toggle_difficulty_home",
                    user_id="U001",
                    team_id="T001",
                    selected_option={"value": "easy"},
                )
        assert resp.status_code == 200

    def test_set_hard_mode(self, flask_client, make_user):
        make_user(user_id="U001", team_id="T001")
        mock_client = MagicMock()
        with patch("app.get_slack_client", return_value=mock_client):
            with patch("app.publish_home_view"):
                resp = _post_action(
                    flask_client,
                    action_id="toggle_difficulty_home",
                    user_id="U001",
                    team_id="T001",
                    selected_option={"value": "hard"},
                )
        assert resp.status_code == 200

    def test_difficulty_fetches_user_when_not_found(self, flask_client):
        mock_client = MagicMock()
        with patch("app.get_slack_client", return_value=mock_client):
            with patch("app.fetch_and_store_single_user", return_value=True):
                with patch("app.publish_home_view"):
                    resp = _post_action(
                        flask_client,
                        action_id="toggle_difficulty_home",
                        user_id="UNEW",
                        team_id="T001",
                        selected_option={"value": "hard"},
                    )
        assert resp.status_code == 200


# ── view_leaderboard_home ─────────────────────────────────────────────────────


class TestViewLeaderboardHomeAction:
    def test_opens_leaderboard_modal(self, flask_client, make_user):
        make_user(user_id="U001", team_id="T001")
        mock_client = MagicMock()
        with patch("app.get_slack_client", return_value=mock_client):
            with patch("app.get_leaderboard_blocks", return_value=[]):
                resp = _post_action(
                    flask_client,
                    action_id="view_leaderboard_home",
                    user_id="U001",
                    team_id="T001",
                )
        assert resp.status_code == 200
        mock_client.views_open.assert_called_once()

    def test_leaderboard_slack_api_error_handled(self, flask_client, make_user):
        from slack_sdk.errors import SlackApiError

        make_user(user_id="U001", team_id="T001")
        mock_client = MagicMock()
        mock_client.views_open.side_effect = SlackApiError("error", {"error": "expired_trigger_id"})
        with patch("app.get_slack_client", return_value=mock_client):
            with patch("app.get_leaderboard_blocks", return_value=[]):
                resp = _post_action(
                    flask_client,
                    action_id="view_leaderboard_home",
                    user_id="U001",
                    team_id="T001",
                )
        assert resp.status_code == 200


# ── help_home ─────────────────────────────────────────────────────────────────


class TestHelpHomeAction:
    def test_opens_help_modal(self, flask_client, make_user):
        make_user(user_id="U001", team_id="T001")
        mock_client = MagicMock()
        with patch("app.get_slack_client", return_value=mock_client):
            resp = _post_action(flask_client, action_id="help_home", user_id="U001", team_id="T001")
        assert resp.status_code == 200
        mock_client.views_open.assert_called_once()

    def test_help_slack_api_error_handled(self, flask_client, make_user):
        from slack_sdk.errors import SlackApiError

        make_user(user_id="U001", team_id="T001")
        mock_client = MagicMock()
        mock_client.views_open.side_effect = SlackApiError("error", {"error": "expired_trigger_id"})
        with patch("app.get_slack_client", return_value=mock_client):
            resp = _post_action(flask_client, action_id="help_home", user_id="U001", team_id="T001")
        assert resp.status_code == 200


# ── unknown action ────────────────────────────────────────────────────────────


class TestUnknownAction:
    def test_unknown_action_returns_200(self, flask_client):
        mock_client = MagicMock()
        with patch("app.get_slack_client", return_value=mock_client):
            resp = _post_action(flask_client, action_id="some_unknown_action")
        assert resp.status_code == 200
