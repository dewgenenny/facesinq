"""Unit tests for leaderboard.py — block-building logic only."""

from leaderboard import create_ranking_section


def _score(name="Alice", pct=80.0, image="http://img", score=100, attempts=10, streak=0):
    return (name, pct, image, score, attempts, streak)


class TestCreateRankingSection:
    def test_empty_scores_shows_empty_message(self):
        blocks = create_ranking_section("Title", [])
        texts = [b.get("text", {}).get("text", "") for b in blocks]
        assert any("No scores yet" in t for t in texts)

    def test_empty_scores_custom_message(self):
        blocks = create_ranking_section("Title", [], empty_message="Nothing here.")
        texts = [b.get("text", {}).get("text", "") for b in blocks]
        assert any("Nothing here." in t for t in texts)

    def test_header_text_is_present(self):
        blocks = create_ranking_section("My Header", [])
        header_texts = [b["text"]["text"] for b in blocks if b.get("type") == "header"]
        assert "My Header" in header_texts

    def test_gold_medal_for_first(self):
        blocks = create_ranking_section("Title", [_score("Alice")])
        section_texts = [
            b["text"]["text"] for b in blocks if b.get("type") == "section" and "text" in b
        ]
        assert any("🥇" in t for t in section_texts)

    def test_silver_medal_for_second(self):
        scores = [_score("Alice"), _score("Bob", score=80)]
        blocks = create_ranking_section("Title", scores)
        section_texts = [
            b["text"]["text"] for b in blocks if b.get("type") == "section" and "text" in b
        ]
        assert any("🥈" in t for t in section_texts)

    def test_bronze_medal_for_third(self):
        scores = [_score("A"), _score("B", score=80), _score("C", score=60)]
        blocks = create_ranking_section("Title", scores)
        section_texts = [
            b["text"]["text"] for b in blocks if b.get("type") == "section" and "text" in b
        ]
        assert any("🥉" in t for t in section_texts)

    def test_numeric_rank_for_fourth(self):
        scores = [_score(f"P{i}", score=100 - i * 10) for i in range(4)]
        blocks = create_ranking_section("Title", scores)
        section_texts = [
            b["text"]["text"] for b in blocks if b.get("type") == "section" and "text" in b
        ]
        assert any("4." in t for t in section_texts)

    def test_streak_shown_when_greater_than_one(self):
        blocks = create_ranking_section("Title", [_score("Alice", streak=5)])
        section_texts = [
            b["text"]["text"] for b in blocks if b.get("type") == "section" and "text" in b
        ]
        assert any("🔥" in t and "5" in t for t in section_texts)

    def test_streak_hidden_when_zero_or_one(self):
        for streak in (0, 1):
            blocks = create_ranking_section("Title", [_score("Alice", streak=streak)])
            section_texts = [
                b["text"]["text"] for b in blocks if b.get("type") == "section" and "text" in b
            ]
            assert not any("🔥" in t for t in section_texts)

    def test_image_accessory_added_when_url_present(self):
        blocks = create_ranking_section("Title", [_score(image="http://img/photo.jpg")])
        sections_with_accessory = [
            b for b in blocks if b.get("type") == "section" and "accessory" in b
        ]
        assert len(sections_with_accessory) == 1
        assert sections_with_accessory[0]["accessory"]["type"] == "image"

    def test_no_image_accessory_when_url_empty(self):
        blocks = create_ranking_section("Title", [_score(image=None)])
        sections_with_accessory = [
            b for b in blocks if b.get("type") == "section" and "accessory" in b
        ]
        assert len(sections_with_accessory) == 0
