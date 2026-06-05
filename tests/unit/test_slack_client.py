"""Tests for slack_client functions."""

from unittest.mock import MagicMock, patch

from slack_sdk.errors import SlackApiError


class TestGetSlackClient:
    def test_returns_default_client_when_no_team_id(self):
        from slack_client import get_slack_client

        client = get_slack_client()
        assert client is not None

    def test_returns_workspace_client_when_token_found(self, make_workspace):
        make_workspace(team_id="T001", token="xoxb-workspace-token")
        from slack_client import get_slack_client

        client = get_slack_client("T001")
        assert client is not None

    def test_falls_back_to_default_when_no_token(self):
        from slack_client import get_slack_client

        with patch("slack_client.get_workspace_access_token", side_effect=Exception("not found")):
            client = get_slack_client("TNONE")
        assert client is not None

    def test_falls_back_when_token_is_none(self):
        from slack_client import get_slack_client

        with patch("slack_client.get_workspace_access_token", return_value=None):
            client = get_slack_client("T001")
        assert client is not None


class TestHandleSlackEvent:
    def test_team_join_adds_user(self, make_workspace):
        make_workspace(team_id="T001")
        from slack_client import handle_slack_event

        event = {
            "type": "team_join",
            "user": {
                "id": "UNEW",
                "real_name": "New Person",
                "is_bot": False,
                "deleted": False,
                "profile": {"image_512": "http://example.com/img.jpg"},
            },
        }
        with patch("slack_client.add_or_update_user") as mock_add:
            handle_slack_event(event, "T001")
        mock_add.assert_called_once()

    def test_team_join_skips_bot(self):
        from slack_client import handle_slack_event

        event = {
            "type": "team_join",
            "user": {
                "id": "UBOT",
                "real_name": "Bot",
                "is_bot": True,
                "deleted": False,
                "profile": {},
            },
        }
        with patch("slack_client.add_or_update_user") as mock_add:
            handle_slack_event(event, "T001")
        mock_add.assert_not_called()

    def test_app_home_opened_publishes_view(self, make_user):
        make_user(user_id="U001", team_id="T001")
        from slack_client import handle_slack_event

        event = {"type": "app_home_opened", "user": "U001"}
        mock_client = MagicMock()
        with patch("slack_client.get_slack_client", return_value=mock_client):
            with patch("slack_client.publish_home_view") as mock_publish:
                handle_slack_event(event, "T001")
        mock_publish.assert_called_once_with("U001", "T001", mock_client)

    def test_unhandled_event_type_does_not_raise(self):
        from slack_client import handle_slack_event

        event = {"type": "some_unknown_event"}
        handle_slack_event(event, "T001")  # Should not raise

    def test_user_change_updates_user(self):
        from slack_client import handle_slack_event

        event = {
            "type": "user_change",
            "user": {
                "id": "U001",
                "real_name": "Updated Name",
                "is_bot": False,
                "deleted": False,
                "profile": {"image_512": "http://example.com/img.jpg"},
            },
        }
        with patch("slack_client.add_or_update_user") as mock_add:
            handle_slack_event(event, "T001")
        mock_add.assert_called_once()


class TestIsUserWorkspaceAdmin:
    def test_returns_true_for_admin(self, make_workspace):
        make_workspace(team_id="T001")
        from slack_client import is_user_workspace_admin

        mock_client = MagicMock()
        mock_client.users_info.return_value = {
            "ok": True,
            "user": {"is_admin": True, "is_owner": False},
        }
        with patch("slack_client.get_slack_client", return_value=mock_client):
            result = is_user_workspace_admin("U001", "T001")
        assert result is True

    def test_returns_true_for_owner(self, make_workspace):
        make_workspace(team_id="T001")
        from slack_client import is_user_workspace_admin

        mock_client = MagicMock()
        mock_client.users_info.return_value = {
            "ok": True,
            "user": {"is_admin": False, "is_owner": True},
        }
        with patch("slack_client.get_slack_client", return_value=mock_client):
            result = is_user_workspace_admin("U001", "T001")
        assert result is True

    def test_returns_false_for_regular_user(self, make_workspace):
        make_workspace(team_id="T001")
        from slack_client import is_user_workspace_admin

        mock_client = MagicMock()
        mock_client.users_info.return_value = {
            "ok": True,
            "user": {"is_admin": False, "is_owner": False},
        }
        with patch("slack_client.get_slack_client", return_value=mock_client):
            result = is_user_workspace_admin("U001", "T001")
        assert result is False

    def test_returns_false_on_api_failure(self, make_workspace):
        make_workspace(team_id="T001")
        from slack_client import is_user_workspace_admin

        mock_client = MagicMock()
        mock_client.users_info.return_value = {"ok": False, "error": "user_not_found"}
        with patch("slack_client.get_slack_client", return_value=mock_client):
            result = is_user_workspace_admin("U001", "T001")
        assert result is False

    def test_returns_false_on_api_not_ok(self, make_workspace):
        make_workspace(team_id="T001")
        from slack_client import is_user_workspace_admin

        mock_client = MagicMock()
        mock_client.users_info.side_effect = SlackApiError("error", {"error": "not_authed"})
        with patch("slack_client.get_slack_client", return_value=mock_client):
            result = is_user_workspace_admin("U001", "T001")
        assert result is False


class TestHandleSlackOAuthRedirect:
    def test_success_returns_true(self):
        from slack_client import handle_slack_oauth_redirect

        mock_response = {
            "ok": True,
            "team": {"id": "T001", "name": "My Workspace"},
            "access_token": "xoxb-new-token",
        }
        with patch("slack_client.client") as mock_client:
            mock_client.oauth_v2_access.return_value = mock_response
            with patch("slack_client.add_workspace"):
                with patch("slack_client.fetch_and_store_users"):
                    success, msg = handle_slack_oauth_redirect("auth_code_123")
        assert success is True
        assert msg == "Installation Successful!"

    def test_failure_returns_false(self):
        from slack_client import handle_slack_oauth_redirect

        mock_response = {"ok": False, "error": "invalid_code"}
        with patch("slack_client.client") as mock_client:
            mock_client.oauth_v2_access.return_value = mock_response
            success, msg = handle_slack_oauth_redirect("bad_code")
        assert success is False

    def test_slack_api_error_returns_false(self):
        from slack_client import handle_slack_oauth_redirect

        with patch("slack_client.client") as mock_client:
            mock_client.oauth_v2_access.side_effect = SlackApiError(
                "error", {"error": "invalid_auth"}
            )
            success, msg = handle_slack_oauth_redirect("code")
        assert success is False
        assert "OAuth flow failed" in msg

    def test_generic_exception_returns_false(self):
        from slack_client import handle_slack_oauth_redirect

        with patch("slack_client.client") as mock_client:
            mock_client.oauth_v2_access.side_effect = RuntimeError("Unexpected")
            success, msg = handle_slack_oauth_redirect("code")
        assert success is False
