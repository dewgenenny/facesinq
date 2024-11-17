# game_manager.py
import random
from slack_client import get_slack_client
from database_helpers import create_or_update_quiz_session, get_colleagues_excluding_user, update_score, get_active_quiz_session
from slack_sdk.errors import SlackApiError
from models import User

client = get_slack_client()

def send_quiz_to_user(user_id):
    """Send a quiz to a user by creating quiz options and posting them to Slack."""

    # Fetch colleagues excluding the user themselves
    colleagues = get_colleagues_excluding_user(user_id)

    # Check if the user already has an active quiz session
    existing_quiz = get_active_quiz_session(user_id)
    if existing_quiz:
        print(f"User {user_id} already has an active quiz.")
        try:
            client.chat_postMessage(
                channel=user_id,
                text="You already have an active quiz! Please answer it before requesting a new one."
            )
        except SlackApiError as e:
            print(f"Error sending message to user {user_id}: {e.response['error']}")
        return

    # Check if there are enough colleagues for a quiz
    if len(colleagues) < 4:
        print(f"Not enough colleagues to send a quiz to user {user_id}")
        return

    # Select correct answer and random options
    correct_choice = random.choice(colleagues)
    options = [correct_choice] + random.sample([col for col in colleagues if col != correct_choice], 3)
    random.shuffle(options)

    # Store the correct answer in quiz_sessions
    create_or_update_quiz_session(user_id, correct_choice.id)

    # Build the Slack message with interactive buttons
    blocks = [
        # Text prompt
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Who's this colleague?*"
            }
        },
        # Image block (optional)
        {
            "type": "image",
            "image_url": correct_choice.image or "https://via.placeholder.com/600",
            "alt_text": "Image of a colleague"
        },
        # Answer buttons with a block_id
        {
            "type": "actions",
            "block_id": "answer_buttons",  # Assign a block_id
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": option.name},
                    "value": option.id,
                    "action_id": f"quiz_response_{idx}"
                }
                for idx, option in enumerate(options)
            ]
        }
    ]

    # Send the message to the user
    try:
        response = client.chat_postMessage(
            channel=user_id,
            text="Time for a quiz!",
            blocks=blocks
        )
        print(f"Message sent to user {user_id}, ts: {response['ts']}")
    except SlackApiError as e:
        print(f"Error sending message to {user_id}: {e.response['error']}")

def handle_quiz_response(user_id, selected_user_id):
    """Handles the user's quiz response and updates scores."""

    # Fetch the user's active quiz session
    quiz_session = get_active_quiz_session(user_id)
    if not quiz_session:
        print(f"No active quiz session for user {user_id}")
        return

    # Check if the selected answer is correct
    is_correct = quiz_session.correct_user_id == selected_user_id
    if is_correct:
        update_score(user_id, points=10)
        response_text = "Correct! 🎉 You've earned 10 points!"
    else:
        response_text = "Oops, that's incorrect. Better luck next time!"

    # Inform the user of the result
    try:
        client.chat_postMessage(
            channel=user_id,
            text=response_text
        )
    except SlackApiError as e:
        print(f"Error sending quiz response message to user {user_id}: {e.response['error']}")
