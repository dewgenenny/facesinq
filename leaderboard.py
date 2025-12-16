
from db import  Session
from database_helpers import get_top_scores
import logging
import logging

logging.basicConfig(level=logging.INFO)

def get_leaderboard_blocks():
    # Get the top scores from the database
    top_scores = get_top_scores(10)

    # Construct the leaderboard blocks
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🏆 Leaderboard",
                "emoji": True
            }
        },
        {
            "type": "divider"
        }
    ]

    if not top_scores:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "_No scores available yet._"
            }
        })
    else:
        for idx, (name, score, image_url) in enumerate(top_scores):
            section = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{idx + 1}. {name}*\n{score} points"
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