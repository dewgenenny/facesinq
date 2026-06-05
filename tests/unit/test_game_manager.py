"""Tests for game_manager functions."""

from unittest.mock import MagicMock, patch


class TestPrepareNextQuiz:
    def test_stores_quiz_in_pending_when_successful(self, make_user):
        for i in range(5):
            make_user(user_id=f"U{i:03d}", name=f"Person{i}", team_id="T001")

        from game_manager import PENDING_QUIZZES, prepare_next_quiz

        PENDING_QUIZZES.pop("U000", None)
        prepare_next_quiz("U000", "T001")
        assert "U000" in PENDING_QUIZZES
        PENDING_QUIZZES.pop("U000", None)

    def test_no_entry_when_not_enough_colleagues(self, make_user):
        make_user(user_id="U001", team_id="T001")

        from game_manager import PENDING_QUIZZES, prepare_next_quiz

        PENDING_QUIZZES.pop("U001", None)
        prepare_next_quiz("U001", "T001")
        assert "U001" not in PENDING_QUIZZES

    def test_no_entry_for_unknown_user(self):
        from game_manager import PENDING_QUIZZES, prepare_next_quiz

        PENDING_QUIZZES.pop("UNOPE", None)
        prepare_next_quiz("UNOPE", "T001")
        assert "UNOPE" not in PENDING_QUIZZES


class TestSendQuizToUser:
    def test_returns_false_when_active_session_exists(self, make_user):
        make_user(user_id="U001", team_id="T001")
        from database_helpers import create_or_update_quiz_session

        create_or_update_quiz_session("U001", "U002")

        from game_manager import send_quiz_to_user

        with patch("game_manager.get_slack_client") as mock_client:
            mock_client.return_value = MagicMock()
            success, msg = send_quiz_to_user("U001", "T001")
        assert success is False
        assert "active quiz" in msg.lower()

    def test_returns_false_when_not_enough_colleagues(self, make_user):
        make_user(user_id="U001", team_id="T001")

        from game_manager import send_quiz_to_user

        with patch("game_manager.get_slack_client") as mock_client:
            mock_client.return_value = MagicMock()
            success, msg = send_quiz_to_user("U001", "T001")
        assert success is False

    def test_sends_quiz_when_enough_colleagues(self, make_user):
        for i in range(5):
            make_user(user_id=f"U{i:03d}", name=f"Person{i}", team_id="T001")

        from game_manager import send_quiz_to_user

        mock_client = MagicMock()
        mock_client.chat_postMessage.return_value = {"ok": True, "ts": "123.456"}
        with patch("game_manager.get_slack_client", return_value=mock_client):
            success, msg = send_quiz_to_user("U000", "T001")
        assert success is True

    def test_uses_cached_quiz_when_available(self, make_user):
        for i in range(5):
            make_user(user_id=f"U{i:03d}", name=f"Person{i}", team_id="T001")

        from game_manager import PENDING_QUIZZES, generate_quiz_data, send_quiz_to_user

        quiz_data = generate_quiz_data("U000", "T001")
        assert quiz_data is not None
        PENDING_QUIZZES["U000"] = quiz_data

        mock_client = MagicMock()
        mock_client.chat_postMessage.return_value = {"ok": True, "ts": "123.456"}
        with patch("game_manager.get_slack_client", return_value=mock_client):
            success, msg = send_quiz_to_user("U000", "T001")
        assert success is True
        assert "U000" not in PENDING_QUIZZES


class TestSendQuizHardMode:
    def test_hard_mode_generates_grid_and_sends(self, make_user):
        for i in range(5):
            make_user(user_id=f"U{i:03d}", name=f"Person{i}", team_id="T001")

        from database_helpers import update_user_difficulty_mode

        update_user_difficulty_mode("U000", "hard")

        from game_manager import send_quiz_to_user

        mock_client = MagicMock()
        mock_client.chat_postMessage.return_value = {"ok": True, "ts": "123.456"}
        mock_client.files_upload_v2.return_value = {"ok": True, "file": {"permalink": "http://x"}}
        with patch("game_manager.get_slack_client", return_value=mock_client):
            with patch("game_manager.generate_grid_image_bytes", return_value=b"fakegrid"):
                success, msg = send_quiz_to_user("U000", "T001")
        assert success is True

    def test_hard_mode_continues_when_grid_upload_fails(self, make_user):
        from slack_sdk.errors import SlackApiError

        for i in range(5):
            make_user(user_id=f"U{i:03d}", name=f"Person{i}", team_id="T001")

        from database_helpers import update_user_difficulty_mode

        update_user_difficulty_mode("U000", "hard")

        from game_manager import send_quiz_to_user

        mock_client = MagicMock()
        mock_client.chat_postMessage.return_value = {"ok": True, "ts": "123.456"}
        mock_client.files_upload_v2.side_effect = SlackApiError("err", {"error": "upload_failed"})
        with patch("game_manager.get_slack_client", return_value=mock_client):
            with patch("game_manager.generate_grid_image_bytes", return_value=b"fakegrid"):
                # Should not raise despite upload failure
                success, msg = send_quiz_to_user("U000", "T001")
        assert success is True


def _build_quiz_payload(correct_user_id, selected_user_id, option_user_ids, action_idx=0):
    """Build a minimal Slack quiz-response payload dict."""
    elements = [
        {
            "type": "button",
            "action_id": f"quiz_response_{i}",
            "value": uid,
            "text": {"type": "plain_text", "text": f"Person{i}", "emoji": True},
        }
        for i, uid in enumerate(option_user_ids)
    ]
    return {
        "actions": [{"action_id": f"quiz_response_{action_idx}", "value": selected_user_id}],
        "message": {
            "ts": "111.222",
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": "Who is *Alice*?"}},
                {"type": "actions", "elements": elements},
            ],
        },
        "channel": {"id": "D001"},
    }


class TestHandleQuizResponse:
    def test_correct_answer_updates_score_and_message(self, make_user):
        for i in range(5):
            make_user(user_id=f"U{i:03d}", name=f"Person{i}", team_id="T001")

        from database_helpers import create_or_update_quiz_session, get_user_score

        create_or_update_quiz_session("U000", "U001")

        from game_manager import handle_quiz_response

        payload = _build_quiz_payload("U001", "U001", [f"U{i:03d}" for i in range(1, 5)])
        mock_client = MagicMock()
        with patch("game_manager.get_slack_client", return_value=mock_client):
            handle_quiz_response("U000", "U001", payload, "T001")

        mock_client.chat_update.assert_called_once()
        score, attempts, correct = get_user_score("U000")
        assert attempts == 1
        assert correct == 1

    def test_incorrect_answer_updates_score_and_message(self, make_user):
        for i in range(5):
            make_user(user_id=f"U{i:03d}", name=f"Person{i}", team_id="T001")

        from database_helpers import create_or_update_quiz_session, get_user_score

        create_or_update_quiz_session("U000", "U001")

        from game_manager import handle_quiz_response

        # Select U002 but correct is U001
        payload = _build_quiz_payload(
            "U001", "U002", [f"U{i:03d}" for i in range(1, 5)], action_idx=1
        )
        mock_client = MagicMock()
        with patch("game_manager.get_slack_client", return_value=mock_client):
            handle_quiz_response("U000", "U002", payload, "T001")

        mock_client.chat_update.assert_called_once()
        score, attempts, correct = get_user_score("U000")
        assert attempts == 1
        assert correct == 0

    def test_expired_session_sends_expiry_message(self, make_user):
        make_user(user_id="U000", team_id="T001")
        # No quiz session created

        from game_manager import handle_quiz_response

        payload = _build_quiz_payload("U001", "U001", ["U001", "U002", "U003", "U004"])
        mock_client = MagicMock()
        with patch("game_manager.get_slack_client", return_value=mock_client):
            handle_quiz_response("U000", "U001", payload, "T001")

        mock_client.chat_postMessage.assert_called_once()

    def test_streak_increments_on_consecutive_day(self, make_user):
        from datetime import datetime, timedelta

        for i in range(5):
            make_user(user_id=f"U{i:03d}", name=f"Person{i}", team_id="T001")

        from database_helpers import create_or_update_quiz_session, update_user_streak

        # Set last_answered to yesterday
        yesterday = datetime.utcnow() - timedelta(days=1)
        update_user_streak("U000", 3, yesterday)
        create_or_update_quiz_session("U000", "U001")

        from database_helpers import get_user
        from game_manager import handle_quiz_response

        payload = _build_quiz_payload("U001", "U001", [f"U{i:03d}" for i in range(1, 5)])
        mock_client = MagicMock()
        with patch("game_manager.get_slack_client", return_value=mock_client):
            handle_quiz_response("U000", "U001", payload, "T001")

        user = get_user("U000")
        assert user.current_streak == 4

    def test_streak_resets_after_missed_day(self, make_user):
        from datetime import datetime, timedelta

        for i in range(5):
            make_user(user_id=f"U{i:03d}", name=f"Person{i}", team_id="T001")

        from database_helpers import create_or_update_quiz_session, update_user_streak

        # Last answered two days ago — missed a day
        two_days_ago = datetime.utcnow() - timedelta(days=2)
        update_user_streak("U000", 5, two_days_ago)
        create_or_update_quiz_session("U000", "U001")

        from database_helpers import get_user
        from game_manager import handle_quiz_response

        payload = _build_quiz_payload("U001", "U001", [f"U{i:03d}" for i in range(1, 5)])
        mock_client = MagicMock()
        with patch("game_manager.get_slack_client", return_value=mock_client):
            handle_quiz_response("U000", "U001", payload, "T001")

        user = get_user("U000")
        assert user.current_streak == 1

    def test_chat_update_api_error_handled(self, make_user):
        from slack_sdk.errors import SlackApiError

        for i in range(5):
            make_user(user_id=f"U{i:03d}", name=f"Person{i}", team_id="T001")

        from database_helpers import create_or_update_quiz_session

        create_or_update_quiz_session("U000", "U001")

        from game_manager import handle_quiz_response

        payload = _build_quiz_payload("U001", "U001", [f"U{i:03d}" for i in range(1, 5)])
        mock_client = MagicMock()
        mock_client.chat_update.side_effect = SlackApiError("err", {"error": "channel_not_found"})
        with patch("game_manager.get_slack_client", return_value=mock_client):
            handle_quiz_response("U000", "U001", payload, "T001")  # Should not raise


class TestProcessRandomQuizzes:
    def test_no_users_due_does_not_call_send(self):
        # get_users_due_for_quiz is imported inside process_random_quizzes, so patch there
        from game_manager import process_random_quizzes

        with patch("database_helpers.get_users_due_for_quiz", return_value=[]):
            with patch("game_manager.send_quiz_to_user") as mock_send:
                process_random_quizzes()
        mock_send.assert_not_called()

    def test_sends_quiz_to_due_users(self, make_user):
        make_user(user_id="U001", team_id="T001")
        from game_manager import process_random_quizzes

        mock_user = MagicMock()
        mock_user.id = "U001"
        mock_user.team_id = "T001"

        with patch("database_helpers.get_users_due_for_quiz", return_value=[mock_user]):
            with patch("game_manager.send_quiz_to_user", return_value=(True, "ok")):
                with patch("database_helpers.update_user_quiz_schedule"):
                    process_random_quizzes()
