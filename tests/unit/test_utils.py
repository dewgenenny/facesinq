"""Unit tests for utils.py — pure functions only, no I/O."""

from utils import extract_user_id_from_text, should_skip_user


class TestExtractUserIdFromText:
    def test_slack_mention_format(self):
        assert extract_user_id_from_text("<@U12345ABC>") == "U12345ABC"

    def test_slack_mention_lowercase_input(self):
        # Function uppercases the text before matching
        assert extract_user_id_from_text("<@u12345abc>") == "U12345ABC"

    def test_raw_user_id(self):
        assert extract_user_id_from_text("U12345ABC") == "U12345ABC"

    def test_raw_user_id_lowercase(self):
        # Lower-case raw ID gets uppercased; starts with 'U' after upper
        assert extract_user_id_from_text("u12345abc") == "U12345ABC"

    def test_no_match_returns_none(self):
        assert extract_user_id_from_text("hello world") is None

    def test_empty_string_returns_none(self):
        assert extract_user_id_from_text("") is None

    def test_whitespace_stripped(self):
        assert extract_user_id_from_text("  <@U999>  ") == "U999"

    def test_none_input_returns_none(self):
        # Should not raise; exception path returns None
        assert extract_user_id_from_text(None) is None


class TestShouldSkipUser:
    def _user(self, *, is_bot=False, deleted=False, image="http://example.com/photo.jpg"):
        return {
            "is_bot": is_bot,
            "deleted": deleted,
            "profile": {
                "image_512": image,
            },
        }

    def test_normal_user_not_skipped(self):
        assert should_skip_user(self._user()) is False

    def test_bot_is_skipped(self):
        assert should_skip_user(self._user(is_bot=True)) is True

    def test_deleted_user_is_skipped(self):
        assert should_skip_user(self._user(deleted=True)) is True

    def test_no_image_is_skipped(self):
        assert should_skip_user(self._user(image="")) is True

    def test_gravatar_image_is_skipped(self):
        gravatar = "https://secure.gravatar.com/avatar/abc123?s=512"
        assert should_skip_user(self._user(image=gravatar)) is True

    def test_gravatar_bypass_attempt_is_skipped(self):
        # A subdomain that contains "gravatar" but isn't the gravatar host
        # The old substring check would fail here; urlparse hostname check should be safe
        non_gravatar = "https://notsecure.gravatar.com.evil.com/photo.jpg"
        # hostname is notsecure.gravatar.com.evil.com — NOT secure.gravatar.com → not skipped
        assert should_skip_user(self._user(image=non_gravatar)) is False

    def test_fallback_image_fields(self):
        user = {
            "is_bot": False,
            "deleted": False,
            "profile": {
                "image_512": None,
                "image_192": None,
                "image_72": "http://example.com/small.jpg",
            },
        }
        assert should_skip_user(user) is False

    def test_all_image_fields_empty_is_skipped(self):
        user = {
            "is_bot": False,
            "deleted": False,
            "profile": {
                "image_512": None,
                "image_192": None,
                "image_72": "",
            },
        }
        assert should_skip_user(user) is True
