
from slack_sdk.errors import SlackApiError
from db import  Session
from database_helpers import get_top_scores
from slack_client import get_slack_client
import logging

logging.basicConfig(level=logging.INFO)

def send_leaderboard(channel_id, user_id=None):
    # Get the Slack client
    client = get_slack_client()

    # Check if the channel ID starts with 'D' indicating a DM
    if channel_id.startswith('D') and user_id:
        try:
            # Open a DM channel with the user if it doesn't already exist
            response = client.conversations_open(users=user_id)
            channel_id = response['channel']['id']  # Update channel_id to the newly opened DM channel ID
        except SlackApiError as e:
            logging.error(f"Error opening DM with user {user_id}: {e.response['error']}")
            return

    # Get the top scores from the database
    top_scores = get_top_scores(10)

    # Construct the leaderboard message
    leaderboard_text = "*🏆 Leaderboard:*\n"
    if not top_scores:
        leaderboard_text += "_No scores available yet._"
    else:
        for idx, (name, score) in enumerate(top_scores):
            leaderboard_text += f"{idx + 1}. {name} - {score} points\n"

    # Send the leaderboard message to Slack
    try:
        client.chat_postMessage(
            channel=channel_id,  # Use the updated channel_id, which may now point to the DM channel
            text=leaderboard_text
        )
    except SlackApiError as e:
        logging.error(f"Error sending leaderboard: {e.response['error']}")