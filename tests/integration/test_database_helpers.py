"""Integration tests for database_helpers.py against a real SQLite DB."""

import pytest

from database_helpers import (
    add_or_update_user,
    add_workspace,
    create_or_update_quiz_session,
    delete_quiz_session,
    delete_user_score,
    does_user_exist,
    does_workspace_exist,
    get_active_quiz_session,
    get_colleagues_excluding_user,
    get_global_stats,
    get_opted_in_user_count,
    get_user,
    get_user_attempts,
    get_user_name,
    get_user_score,
    get_users_due_for_quiz,
    get_workspace_access_token,
    has_user_opted_in,
    reset_quiz_session,
    update_score,
    update_user_difficulty_mode,
    update_user_opt_in,
    wipe_all_scores,
)

# ── Workspace ────────────────────────────────────────────────────────────────


class TestWorkspace:
    def test_add_and_exists(self, make_workspace):
        make_workspace(team_id="T100")
        assert does_workspace_exist("T100") is True

    def test_nonexistent_workspace(self):
        assert does_workspace_exist("TNOPE") is False

    def test_get_access_token_roundtrip(self, make_workspace):
        make_workspace(team_id="T200", token="xoxb-secret-token")
        token = get_workspace_access_token("T200")
        assert token == "xoxb-secret-token"

    def test_missing_workspace_raises(self):
        with pytest.raises(ValueError):
            get_workspace_access_token("TNOPE")

    def test_update_existing_workspace(self, make_workspace):
        make_workspace(team_id="T300", name="Old Name", token="old-token")
        add_workspace("T300", "New Name", "new-token")
        assert get_workspace_access_token("T300") == "new-token"


# ── User ─────────────────────────────────────────────────────────────────────


class TestUser:
    def test_add_user_and_exists(self, make_user):
        make_user(user_id="U001", team_id="T001")
        assert does_user_exist("T001") is True

    def test_no_users_for_team(self):
        assert does_user_exist("TNOPE") is False

    def test_get_user_name(self, make_user):
        make_user(user_id="U002", name="Diana")
        assert get_user_name("U002") == "Diana"

    def test_get_user_name_unknown(self):
        assert get_user_name("UNOPE") == "Unknown"

    def test_update_user_name(self, make_user):
        make_user(user_id="U003", name="Old Name", team_id="T001")
        add_or_update_user("U003", "New Name", "http://img", "T001")
        assert get_user_name("U003") == "New Name"

    def test_get_user_returns_none_for_missing(self):
        assert get_user("UNOPE") is None


# ── Opt-in ───────────────────────────────────────────────────────────────────


class TestOptIn:
    def test_opt_in_user(self, make_user):
        make_user(user_id="U010")
        update_user_opt_in("U010", True)
        assert has_user_opted_in("U010") is True

    def test_opt_out_user(self, make_user):
        make_user(user_id="U011")
        update_user_opt_in("U011", True)
        update_user_opt_in("U011", False)
        assert has_user_opted_in("U011") is False

    def test_opt_in_returns_false_for_missing_user(self):
        result = update_user_opt_in("UNOPE", True)
        assert result is False

    def test_has_opted_in_false_for_missing_user(self):
        assert has_user_opted_in("UNOPE") is False

    def test_opted_in_count(self, make_user):
        make_user(user_id="U020", team_id="T010")
        make_user(user_id="U021", team_id="T010")
        update_user_opt_in("U020", True)
        assert get_opted_in_user_count("T010") == 1

    def test_opted_in_count_empty_team(self):
        assert get_opted_in_user_count("TNONE") == 0


# ── Scores ───────────────────────────────────────────────────────────────────


class TestScores:
    def test_initial_score_zero(self, make_user):
        make_user(user_id="U030")
        score, attempts, correct = get_user_score("U030")
        assert score == 0 and attempts == 0 and correct == 0

    def test_score_missing_user_returns_zeros(self):
        assert get_user_score("UNOPE") == (0, 0, 0)

    def test_update_score_correct(self, make_user):
        make_user(user_id="U031")
        update_score("U031", 10, is_correct=True)
        score, attempts, correct = get_user_score("U031")
        assert score == 10
        assert attempts == 1
        assert correct == 1

    def test_update_score_incorrect(self, make_user):
        make_user(user_id="U032")
        update_score("U032", 2, is_correct=False)
        score, attempts, correct = get_user_score("U032")
        assert score == 2
        assert attempts == 1
        assert correct == 0

    def test_accumulates_score(self, make_user):
        make_user(user_id="U033")
        update_score("U033", 10, is_correct=True)
        update_score("U033", 10, is_correct=True)
        score, attempts, correct = get_user_score("U033")
        assert score == 20
        assert attempts == 2
        assert correct == 2

    def test_get_user_attempts(self, make_user):
        make_user(user_id="U034")
        update_score("U034", 10)
        update_score("U034", 10)
        assert get_user_attempts("U034") == 2

    def test_get_user_attempts_missing(self):
        assert get_user_attempts("UNOPE") == 0


# ── Quiz sessions ─────────────────────────────────────────────────────────────


class TestQuizSession:
    def test_create_and_get_active_session(self, make_user):
        make_user(user_id="U040")
        create_or_update_quiz_session("U040", "U_CORRECT")
        session = get_active_quiz_session("U040")
        assert session is not None
        assert session.correct_user_id == "U_CORRECT"

    def test_no_active_session(self):
        assert get_active_quiz_session("UNOPE") is None

    def test_delete_quiz_session(self, make_user):
        make_user(user_id="U041")
        create_or_update_quiz_session("U041", "U_CORRECT")
        delete_quiz_session("U041")
        assert get_active_quiz_session("U041") is None

    def test_reset_quiz_session(self, make_user):
        make_user(user_id="U042")
        create_or_update_quiz_session("U042", "U_C")
        reset_quiz_session("U042")
        assert get_active_quiz_session("U042") is None

    def test_create_replaces_existing_session(self, make_user):
        make_user(user_id="U043")
        create_or_update_quiz_session("U043", "U_FIRST")
        create_or_update_quiz_session("U043", "U_SECOND")
        session = get_active_quiz_session("U043")
        assert session.correct_user_id == "U_SECOND"


# ── Colleagues ────────────────────────────────────────────────────────────────


class TestColleagues:
    def test_excludes_self(self, make_user):
        for uid in ("U050", "U051", "U052"):
            make_user(user_id=uid, team_id="T050")
        colleagues = get_colleagues_excluding_user("U050", "T050")
        ids = [c.id for c in colleagues]
        assert "U050" not in ids
        assert "U051" in ids and "U052" in ids

    def test_excludes_other_teams(self, make_user):
        make_user(user_id="U060", team_id="T060")
        make_user(user_id="U061", team_id="T061")
        colleagues = get_colleagues_excluding_user("U060", "T060")
        assert all(c.team_id == "T060" for c in colleagues)


# ── Delete score ──────────────────────────────────────────────────────────────


class TestDeleteScore:
    def test_delete_score_clears_data(self, make_user):
        make_user(user_id="U070")
        update_score("U070", 10, is_correct=True)
        create_or_update_quiz_session("U070", "U_C")
        assert delete_user_score("U070") is True
        assert get_user_score("U070") == (0, 0, 0)
        assert get_active_quiz_session("U070") is None


# ── Difficulty mode ───────────────────────────────────────────────────────────


class TestDifficultyMode:
    def test_update_difficulty(self, make_user):
        make_user(user_id="U080")
        assert update_user_difficulty_mode("U080", "hard") is True
        user = get_user("U080")
        assert user.difficulty_mode == "hard"

    def test_update_difficulty_missing_user(self):
        assert update_user_difficulty_mode("UNOPE", "hard") is False


# ── Global stats ──────────────────────────────────────────────────────────────


class TestGlobalStats:
    def test_empty_db_returns_zeros(self):
        stats = get_global_stats()
        assert stats == {"players": 0, "questions": 0, "accuracy": 0.0}

    def test_stats_reflect_scores(self, make_user):
        make_user(user_id="U090")
        update_score("U090", 10, is_correct=True)
        update_score("U090", 2, is_correct=False)
        stats = get_global_stats()
        assert stats["players"] == 1
        assert stats["questions"] == 2
        assert stats["accuracy"] == pytest.approx(50.0)


# ── Wipe all scores ───────────────────────────────────────────────────────────


class TestWipeAllScores:
    def test_wipe_clears_scores(self, make_user):
        make_user(user_id="U100")
        update_score("U100", 10, is_correct=True)
        wipe_all_scores()
        assert get_user_score("U100") == (0, 0, 0)

    def test_wipe_returns_true(self):
        assert wipe_all_scores() is True


# ── Users due for quiz ────────────────────────────────────────────────────────


class TestUsersDueForQuiz:
    def test_opted_in_user_with_no_schedule_is_due(self, make_user):
        make_user(user_id="U110", team_id="T110")
        update_user_opt_in("U110", True)
        due = get_users_due_for_quiz()
        assert any(u.id == "U110" for u in due)

    def test_opted_out_user_not_due(self, make_user):
        make_user(user_id="U111", team_id="T111")
        # opted_in defaults to False
        due = get_users_due_for_quiz()
        assert not any(u.id == "U111" for u in due)
