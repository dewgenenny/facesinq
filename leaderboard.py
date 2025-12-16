
from db import  Session
from database_helpers import get_top_scores
import logging
import logging

logging.basicConfig(level=logging.INFO)

def get_leaderboard_text():
    # Get the top scores from the database
    top_scores = get_top_scores(10)

    # Construct the leaderboard message
    leaderboard_text = "*🏆 Leaderboard:*\n"
    if not top_scores:
        leaderboard_text += "_No scores available yet._"
    else:
        for idx, (name, score) in enumerate(top_scores):
            leaderboard_text += f"{idx + 1}. {name} - {score} points\n"
            
    return leaderboard_text