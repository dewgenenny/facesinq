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
