import os
import random
from slack_sdk.errors import SlackApiError
from sqlalchemy.orm import Session
from db import Session
from models import User, QuizSession
from slack_client import get_slack_client, verify_slack_signature
from database_helpers import get_colleagues_excluding_user, get_active_quiz_session, create_or_update_quiz_session, get_workspace_access_token
# Define quiz_answers at the module level
quiz_answers = {}

# quiz_app.py

from slack_sdk.errors import SlackApiError

from slack_sdk.errors import SlackApiError


def send_quiz():
    global quiz_answers

    # Set up the Slack client
    client = get_slack_client()

    session = Session()

    try:
        # Select users who have opted in to receive quizzes
        recipient_ids = session.query(User.id).filter(User.opted_in == True).all()
        recipient_ids = [user_id[0] for user_id in recipient_ids]

        # Get all colleagues (regardless of opt-in status)
        all_colleagues = session.query(User).all()

        for user_id in recipient_ids:
            # Exclude the user themselves from options
            colleagues = [colleague for colleague in all_colleagues if colleague.id != user_id]
            if len(colleagues) < 4:
                print(f"Not enough colleagues to send a quiz to user {user_id}")
                continue

            correct_choice = random.choice(colleagues)
            options = [correct_choice] + random.sample(
                [col for col in colleagues if col != correct_choice], 3
            )
            random.shuffle(options)

            # Store the correct answer
            quiz_answers[user_id] = correct_choice.id

            # Build interactive message
            blocks = [
                # Text prompt
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Who's this colleague?*"
                    }
                },
                # Larger image block
                {
                    "type": "image",
                    "image_url": correct_choice.image or "https://via.placeholder.com/600",
                    "alt_text": "Image of a colleague"
                },
                # Action buttons
                {
                    "type": "actions",
                    "elements": []
                }
            ]

            # Populate the actions block with options
            for idx, option in enumerate(options):
                blocks[2]["elements"].append({
                    "type": "button",
                    "text": {"type": "plain_text", "text": option.name},
                    "value": option.id,
                    "action_id": f"quiz_response_{idx}"
                })

            # Debugging: Print the blocks payload
            print(f"Sending the following blocks payload to user {user_id}: {blocks}")

            try:
                response = client.chat_postMessage(
                    channel=user_id,
                    text="Time for a quiz!",
                    blocks=blocks
                )
                print(f"Message sent to user {user_id}, ts: {response['ts']}")
            except SlackApiError as e:
                print(f"Error sending message to {user_id}: {e.response['error']}")
    finally:
        session.close()
