from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import sqlite3
import os
from models import User, Score
from db import  Session,   # Import the engine and initialization function


def send_leaderboard(user_id):
    SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
    client = WebClient(token=SLACK_BOT_TOKEN)

    session = Session()
    try:
        # Query the top 10 scores, join with User table for names
        top_scores = session.query(User.name, Score.score).join(Score).order_by(Score.score.desc()).limit(10).all()

        leaderboard_text = "*🏆 Leaderboard:*\n"
        for idx, (name, score) in enumerate(top_scores):
            leaderboard_text += f"{idx + 1}. {name} - {score} points\n"

        # Send leaderboard message to Slack
        try:
            client.chat_postMessage(
                channel=user_id,
                text=leaderboard_text
            )
        except SlackApiError as e:
            print(f"Error sending leaderboard: {e.response['error']}")
    finally:
        session.close()