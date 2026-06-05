"""Tests for utils fetch functions."""

from unittest.mock import MagicMock, patch

import pytest


class TestFetchUsers:
    def test_returns_members_list(self, make_workspace):
        make_workspace(team_id="T001", token="xoxb-token")
        from utils import fetch_users

        mock_client = MagicMock()
        mock_client.users_list.return_value = {
            "ok": True,
            "members": [{"id": "U001"}, {"id": "U002"}],
        }
        with patch("utils.WebClient", return_value=mock_client):
            result = fetch_users("T001")
        assert len(result) == 2

    def test_raises_when_no_access_token(self, make_workspace):
        make_workspace(team_id="T001", token="")
        from utils import fetch_users

        # Patch time.sleep so tenacity's exponential backoff doesn't actually wait
        with patch("time.sleep"):
            with pytest.raises(Exception):
                fetch_users("T001")

    def test_raises_when_response_not_ok(self, make_workspace):
        make_workspace(team_id="T001", token="xoxb-token")
        from utils import fetch_users

        mock_client = MagicMock()
        mock_client.users_list.return_value = {"ok": False, "error": "invalid_auth"}
        with patch("utils.WebClient", return_value=mock_client):
            with patch("time.sleep"):
                with pytest.raises(Exception):
                    fetch_users("T001")


class TestFetchAndStoreSingleUser:
    def test_returns_true_on_success(self, make_workspace):
        make_workspace(team_id="T001", token="xoxb-token")
        from utils import fetch_and_store_single_user

        mock_client = MagicMock()
        mock_client.users_info.return_value = {
            "ok": True,
            "user": {
                "id": "U001",
                "real_name": "Alice",
                "profile": {"image_512": "http://img.jpg"},
            },
        }
        with patch("utils.WebClient", return_value=mock_client):
            with patch("utils.add_or_update_user") as mock_add:
                result = fetch_and_store_single_user("U001", "T001")
        assert result is True
        mock_add.assert_called_once()

    def test_returns_false_when_api_fails(self, make_workspace):
        make_workspace(team_id="T001", token="xoxb-token")
        from utils import fetch_and_store_single_user

        mock_client = MagicMock()
        mock_client.users_info.return_value = {"ok": False, "error": "user_not_found"}
        with patch("utils.WebClient", return_value=mock_client):
            result = fetch_and_store_single_user("U001", "T001")
        assert result is False

    def test_returns_false_on_exception(self, make_workspace):
        make_workspace(team_id="T001", token="xoxb-token")
        from utils import fetch_and_store_single_user

        with patch("utils.get_workspace_access_token", side_effect=RuntimeError("DB error")):
            result = fetch_and_store_single_user("U001", "T001")
        assert result is False

    def test_adds_missing_workspace_using_bot_token(self):
        from utils import fetch_and_store_single_user

        mock_client = MagicMock()
        mock_client.team_info.return_value = {"ok": True, "team": {"name": "MyTeam"}}
        mock_client.users_info.return_value = {
            "ok": True,
            "user": {
                "id": "U001",
                "real_name": "Bob",
                "profile": {"image_512": "http://img.jpg"},
            },
        }
        with patch("utils.get_workspace_access_token", side_effect=ValueError("not found")):
            with patch("utils.WebClient", return_value=mock_client):
                with patch("utils.add_workspace") as mock_add_ws:
                    with patch("utils.add_or_update_user"):
                        result = fetch_and_store_single_user("U001", "TNEW")
        assert result is True
        mock_add_ws.assert_called_once()

    def test_returns_false_when_no_user_in_response(self, make_workspace):
        make_workspace(team_id="T001", token="xoxb-token")
        from utils import fetch_and_store_single_user

        mock_client = MagicMock()
        mock_client.users_info.return_value = {"ok": True, "user": None}
        with patch("utils.WebClient", return_value=mock_client):
            result = fetch_and_store_single_user("U001", "T001")
        assert result is False


class TestFetchAndStoreUsersForAllWorkspaces:
    def test_is_importable(self):
        # The function is mocked at session start in conftest to prevent startup
        # side effects; we just verify it exists and is callable.
        import utils

        assert callable(utils.fetch_and_store_users_for_all_workspaces)
