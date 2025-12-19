from db import Session
from database_helpers import get_top_scores, get_top_scores_period
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)

def create_ranking_section(title, scores, empty_message="_No scores yet._"):
    """Helper to create blocks for a ranking section."""
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": title,
                "emoji": True
            }
        },
        {"type": "divider"}
    ]

    if not scores:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": empty_message
            }
        })
    else:
        for idx, (name, percentage, image_url, score, total_attempts, current_streak) in enumerate(scores):
            # Add medals for top 3
            if idx == 0:
                rank_display = "🥇"
            elif idx == 1:
                rank_display = "🥈"
            elif idx == 2:
                rank_display = "🥉"
            else:
                rank_display = f"{idx + 1}."

            streak_display = f" 🔥 {current_streak}" if current_streak > 1 else ""
            
            section = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{rank_display} {name}*{streak_display}\n{score} pts (from {total_attempts} tries)"
                }
            }
            
            if image_url:
                section["accessory"] = {
                    "type": "image",
                    "image_url": image_url,
                    "alt_text": name
                }
            
            blocks.append(section)
            blocks.append({"type": "divider"})
    
    return blocks

def get_leaderboard_blocks():
    # Calculate time ranges
    now = datetime.utcnow()
    start_of_day = datetime(now.year, now.month, now.day)
    start_of_week = start_of_day - timedelta(days=now.weekday()) # Monday

    # Get scores
    daily_scores = get_top_scores_period(start_of_day, limit=3)
    weekly_scores = get_top_scores_period(start_of_week, limit=3)
    
    # All time requires 10 attempts min, as per original logic in database_helpers.py
    # But for display consistency, we might want to check if we should keep that limit.
    # The original call: get_top_scores(10)
    all_time_scores = get_top_scores(10)

    blocks = []
    
    # Daily
    blocks.extend(create_ranking_section("📅 Daily Top 3", daily_scores))
    blocks.append({"type": "section", "text": {"type": "plain_text", "text": " ", "emoji": True}}) # Spacer around

    # Weekly
    blocks.extend(create_ranking_section("🗓️ Weekly Top 3", weekly_scores))
    blocks.append({"type": "section", "text": {"type": "plain_text", "text": " ", "emoji": True}}) # Spacer around

    # All Time
    blocks.extend(create_ranking_section("🏆 All-Time Legends", all_time_scores, "_Need 10+ attempts to qualify._"))

    # Footer
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": "Keep playing to climb the ranks! Type `/facesinq quiz` to play."
            }
        ]
    })

    return blocks