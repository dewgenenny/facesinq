"""Tests for db.py module-level logic and initialize_database()."""


def test_initialize_database_is_idempotent():
    """Calling initialize_database() when tables already exist should not raise."""
    from db import initialize_database

    initialize_database()
