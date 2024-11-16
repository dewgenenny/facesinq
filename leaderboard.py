from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import sqlite3
import os



def send_leaderboard(user_id):
    SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
    client = WebClient(token=SLACK_BOT_TOKEN)
    conn = sqlite3.connect('facesinq.db')
    c = conn.cursor()
    c.execute('''
        SELECT users.name, scores.score FROM scores
        JOIN users ON users.id = scores.user_id
        ORDER BY scores.score DESC LIMIT 10
    ''')
    top_scores = c.fetchall()

    leaderboard_text = "*🏆 Leaderboard:*\n"
    for idx, (name, score) in enumerate(top_scores):
        leaderboard_text += f"{idx + 1}. {name} - {score} points\n"

    try:
        client.chat_postMessage(
            channel=user_id,  # Replace with your desired channel
            text=leaderboard_text
        )
    except SlackApiError as e:
        print(f"Error sending leaderboard: {e.response['error']}")
    conn.close()
