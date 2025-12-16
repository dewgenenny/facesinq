
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
        for idx, (name, percentage, image_url, score, total_attempts) in enumerate(top_scores):
            # Add medals for top 3
            if idx == 0:
                rank_display = "🥇"
            elif idx == 1:
                rank_display = "🥈"
            elif idx == 2:
                rank_display = "🥉"
            else:
                rank_display = f"{idx + 1}."

            section = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{rank_display} {name}*\n*{percentage:.1f}%* ({score}/{total_attempts})"
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

        # Add footer context
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