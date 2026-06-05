"""Tests for database_helpers functions requiring richer data setup."""

from database_helpers import (
    get_all_workspaces,
    get_fun_stats,
    get_random_user_images,
    get_top_scores,
    get_top_scores_period,
    get_workspace_access_token,
    update_score,
    update_user_quiz_schedule,
    update_user_streak,
)


class TestGetAllWorkspaces:
    def test_returns_empty_when_none(self):
        assert get_all_workspaces() == []

    def test_returns_all_workspaces(self, make_workspace):
        make_workspace(team_id="T001")
        make_workspace(team_id="T002", name="WS2", token="xoxb-2")
        ws = get_all_workspaces()
        ids = [w.id for w in ws]
        assert "T001" in ids
        assert "T002" in ids


class TestGetRandomUserImages:
    def test_no_users_returns_empty(self):
        assert get_random_user_images(3) == []

    def test_returns_images(self, make_user):
        make_user(user_id="U001", image="http://img1.jpg")
        make_user(user_id="U002", image="http://img2.jpg")
        images = get_random_user_images(5)
        assert len(images) == 2
        assert "http://img1.jpg" in images


class TestGetTopScores:
    def test_empty_returns_empty_list(self):
        assert get_top_scores() == []

    def test_user_with_fewer_than_10_attempts_excluded(self, make_user):
        make_user(user_id="U001")
        for _ in range(9):
            update_score("U001", 10, is_correct=True)
        assert get_top_scores() == []

    def test_user_with_10_plus_attempts_included(self, make_user):
        make_user(user_id="U001", name="TopPlayer")
        for _ in range(10):
            update_score("U001", 10, is_correct=True)
        scores = get_top_scores()
        assert len(scores) == 1
        name, pct, image, score, attempts, streak = scores[0]
        assert name == "TopPlayer"
        assert score == 100
        assert attempts == 10

    def test_sorted_by_score_descending(self, make_user):
        make_user(user_id="U001", name="High")
        make_user(user_id="U002", name="Low")
        for _ in range(10):
            update_score("U001", 10, is_correct=True)
        for _ in range(10):
            update_score("U002", 5, is_correct=False)
        scores = get_top_scores()
        assert scores[0][0] == "High"


class TestGetTopScoresPeriod:
    def test_empty_returns_empty(self):
        from datetime import datetime, timedelta

        start = datetime.utcnow() - timedelta(days=1)
        assert get_top_scores_period(start) == []

    def test_scores_in_period_returned(self, make_user):
        from datetime import datetime, timedelta

        make_user(user_id="U001", name="Recent")
        update_score("U001", 10, is_correct=True)
        start = datetime.utcnow() - timedelta(hours=1)
        scores = get_top_scores_period(start)
        assert len(scores) == 1
        assert scores[0][0] == "Recent"

    def test_scores_before_period_excluded(self, make_user):
        from datetime import datetime, timedelta

        make_user(user_id="U001")
        update_score("U001", 10, is_correct=True)
        # Use a future start date — scores should not appear
        future = datetime.utcnow() + timedelta(hours=1)
        scores = get_top_scores_period(future)
        assert scores == []


class TestGetFunStats:
    def test_empty_db_returns_empty_dict(self):
        assert get_fun_stats() == {}

    def test_streak_master_identified(self, make_user):
        make_user(user_id="U001", name="StreakKing")
        update_user_streak("U001", 5, None)
        stats = get_fun_stats()
        assert "streak_master" in stats
        assert stats["streak_master"]["name"] == "StreakKing"
        assert stats["streak_master"]["value"] == 5

    def test_most_dedicated_identified(self, make_user):
        make_user(user_id="U001", name="Dedicated")
        for _ in range(15):
            update_score("U001", 10, is_correct=True)
        stats = get_fun_stats()
        assert "most_dedicated" in stats
        assert stats["most_dedicated"]["name"] == "Dedicated"
        assert stats["most_dedicated"]["value"] == 15


class TestUpdateUserQuizSchedule:
    def test_updates_schedule(self, make_user):
        from datetime import datetime, timedelta

        make_user(user_id="U001")
        next_quiz = datetime.utcnow() + timedelta(hours=2)
        update_user_quiz_schedule("U001", next_quiz)
        from database_helpers import get_user

        user = get_user("U001")
        assert user.next_random_quiz_at is not None

    def test_missing_user_does_not_raise(self):
        from datetime import datetime, timedelta

        # Should silently do nothing
        update_user_quiz_schedule("UNOPE", datetime.utcnow() + timedelta(hours=1))


class TestUpdateUserStreak:
    def test_sets_streak(self, make_user):
        from datetime import datetime

        make_user(user_id="U001")
        now = datetime.utcnow()
        update_user_streak("U001", 3, now)
        from database_helpers import get_user

        user = get_user("U001")
        assert user.current_streak == 3
        assert user.last_answered_at is not None

    def test_missing_user_does_not_raise(self):
        from datetime import datetime

        update_user_streak("UNOPE", 5, datetime.utcnow())


class TestGetWorkspaceAccessToken:
    def test_get_access_token(self, make_workspace):
        make_workspace(team_id="TW01", token="xoxb-secret")
        assert get_workspace_access_token("TW01") == "xoxb-secret"

    def test_all_workspaces_after_add(self, make_workspace):
        make_workspace(team_id="TW02")
        workspaces = get_all_workspaces()
        assert any(w.id == "TW02" for w in workspaces)
