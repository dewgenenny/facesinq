
from slack_sdk.errors import SlackApiError
from db import  Session
from database_helpers import get_top_scores
from slack_client import get_slack_client


def send_leaderboard(user_id):

    # Get the Slack client
    client = get_slack_client()

    # Get the top scores from the database
    top_scores = get_top_scores(10)

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
