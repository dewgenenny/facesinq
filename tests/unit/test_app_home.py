"""Tests for app_home.get_home_view block construction."""

from unittest.mock import MagicMock


class TestGetHomeView:
    def test_returns_home_type(self, make_user):
        make_user(user_id="U001", team_id="T001")
        from app_home import get_home_view

        result = get_home_view("U001", "T001")
        assert result["type"] == "home"
        assert isinstance(result["blocks"], list)
        assert len(result["blocks"]) > 0

    def test_onboarding_state_for_new_user(self, make_user):
        make_user(user_id="U001", team_id="T001")
        from app_home import get_home_view

        result = get_home_view("U001", "T001")
        all_text = str(result["blocks"])
        assert "Welcome" in all_text or "first quiz" in all_text.lower()

    def test_stats_state_after_attempts(self, make_user):
        make_user(user_id="U001", team_id="T001")
        from database_helpers import update_score

        for _ in range(3):
            update_score("U001", 10, is_correct=True)

        from app_home import get_home_view

        result = get_home_view("U001", "T001")
        all_text = str(result["blocks"])
        assert "Stats" in all_text or "Accuracy" in all_text

    def test_unknown_user_still_returns_home(self):
        from app_home import get_home_view

        result = get_home_view("UUNKNOWN", "T001")
        assert result["type"] == "home"
        assert len(result["blocks"]) > 0

    def test_opted_in_user_shows_enabled(self, make_user):
        make_user(user_id="U001", team_id="T001")
        from database_helpers import update_score, update_user_opt_in

        update_user_opt_in("U001", True)
        for _ in range(2):
            update_score("U001", 10, is_correct=True)

        from app_home import get_home_view

        result = get_home_view("U001", "T001")
        all_text = str(result["blocks"])
        assert "Enabled" in all_text

    def test_with_streak_master_stat(self, make_user):
        make_user(user_id="U001", name="KingStreak", team_id="T001")
        from database_helpers import update_user_streak

        update_user_streak("U001", 7, None)

        from app_home import get_home_view

        result = get_home_view("U001", "T001")
        all_text = str(result["blocks"])
        assert "KingStreak" in all_text or "Streak Master" in all_text

    def test_with_top_scores_section(self, make_user):
        for i in range(5):
            make_user(user_id=f"U{i:03d}", name=f"Player{i}", team_id="T001")
        from database_helpers import update_score

        for i in range(5):
            for _ in range(10):
                update_score(f"U{i:03d}", 10, is_correct=True)

        from app_home import get_home_view

        result = get_home_view("U000", "T001")
        assert result["type"] == "home"

    def test_blocks_have_header(self, make_user):
        make_user(user_id="U001")
        from app_home import get_home_view

        result = get_home_view("U001", "T001")
        headers = [b for b in result["blocks"] if b.get("type") == "header"]
        assert len(headers) > 0
        assert any("FaceSinq" in str(h) for h in headers)


class TestPublishHomeView:
    def test_calls_views_publish(self, make_user):
        make_user(user_id="U001", team_id="T001")
        from app_home import publish_home_view

        mock_client = MagicMock()
        publish_home_view("U001", "T001", mock_client)
        mock_client.views_publish.assert_called_once()

    def test_handles_slack_api_error(self, make_user):
        make_user(user_id="U001", team_id="T001")
        from slack_sdk.errors import SlackApiError

        from app_home import publish_home_view

        mock_client = MagicMock()
        mock_client.views_publish.side_effect = SlackApiError("error", {"error": "invalid_blocks"})
        publish_home_view("U001", "T001", mock_client)  # Should not raise

    def test_handles_generic_exception(self, make_user):
        make_user(user_id="U001", team_id="T001")
        from app_home import publish_home_view

        mock_client = MagicMock()
        mock_client.views_publish.side_effect = RuntimeError("Unexpected")
        publish_home_view("U001", "T001", mock_client)  # Should not raise
