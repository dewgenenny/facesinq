"""Unit tests for models.py — encryption helpers and model properties."""

from models import decrypt_value, encrypt_value


class TestEncryptDecrypt:
    def test_roundtrip_string(self):
        original = "Hello, World!"
        assert decrypt_value(encrypt_value(original)) == original

    def test_roundtrip_unicode(self):
        original = "Ünïcödé Nämé"
        assert decrypt_value(encrypt_value(original)) == original

    def test_none_encrypts_to_none(self):
        assert encrypt_value(None) is None

    def test_none_decrypts_to_none(self):
        assert decrypt_value(None) is None

    def test_encrypted_value_differs_from_plaintext(self):
        plain = "secret"
        enc = encrypt_value(plain)
        assert enc != plain

    def test_encrypted_values_are_strings(self):
        enc = encrypt_value("test")
        assert isinstance(enc, str)


class TestUserEncryptionProperties:
    def test_name_property_roundtrip(self, make_user):
        user = make_user(name="Bob Smith")
        assert user.name == "Bob Smith"

    def test_image_property_roundtrip(self, make_user):
        user = make_user(image="https://example.com/pic.jpg")
        assert user.image == "https://example.com/pic.jpg"

    def test_name_stored_encrypted(self, make_user):
        user = make_user(name="Alice")
        assert user.name_encrypted != "Alice"

    def test_image_stored_encrypted(self, make_user):
        user = make_user(image="https://example.com/img.jpg")
        assert user.image_encrypted != "https://example.com/img.jpg"


class TestUserDefaults:
    def test_opted_in_defaults_false(self, make_user):
        user = make_user()
        assert user.opted_in is False

    def test_difficulty_mode_defaults_easy(self, make_user):
        user = make_user()
        assert user.difficulty_mode == "easy"

    def test_repr_includes_name(self, make_user):
        user = make_user(name="Carol")
        assert "Carol" in repr(user)
