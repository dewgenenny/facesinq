# game_manager.py
import random
from slack_client import get_slack_client
from database_helpers import create_or_update_quiz_session, get_colleagues_excluding_user, update_score, get_active_quiz_session, get_user_name, delete_quiz_session
from slack_sdk.errors import SlackApiError
from models import User



def send_quiz_to_user(user_id, team_id):
    """Send a quiz to a specific user in the workspace."""
    global quiz_answers


    # Set up the Slack client with the correct access token
    client = get_slack_client(team_id)

    # Get all colleagues, excluding the user themselves
    colleagues = get_colleagues_excluding_user(user_id, team_id)

    # Check if the user already has an active quiz session
    existing_quiz = get_active_quiz_session(user_id)

    if existing_quiz:
        print(f"User {user_id} already has an active quiz.")
        send_message_to_user(client, user_id, "You already have an active quiz! Please answer it before requesting a new one.")
        return

    # Check if there are enough colleagues for a quiz
    if len(colleagues) < 4:
        print(f"Not enough colleagues to send a quiz to user {user_id}")
        return

    # Select correct answer and random options
    correct_choice = random.choice(colleagues)
    options = [correct_choice] + random.sample(
        [col for col in colleagues if col != correct_choice], 3
    )
    random.shuffle(options)

    # Store the correct answer in quiz_sessions
    quiz_session = create_or_update_quiz_session(user_id=user_id, correct_user_id=correct_choice.id)

    # Build interactive message
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Who's this colleague?*"
            }
        },
        {
            "type": "image",
            "image_url": correct_choice.image or "https://via.placeholder.com/600",
            "alt_text": "Image of a colleague"
        },
        {
            "type": "actions",
            "block_id": "answer_buttons",
            "elements": []
        }
    ]

    for idx, option in enumerate(options):
        blocks[2]["elements"].append({
            "type": "button",
            "text": {"type": "plain_text", "text": option.name},
            "value": option.id,
            "action_id": f"quiz_response_{idx}"
        })

    blocks.append({
        "type": "actions",
        "block_id": "next_quiz_block",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Next Quiz"},
                "value": "next_quiz",
                "action_id": "next_quiz"
            }
        ]
    })

    # Send the message to the user by opening a DM
    try:
        response = client.conversations_open(users=[user_id])
        channel_id = response["channel"]["id"]

        response = client.chat_postMessage(
            channel=channel_id,
            text="Time for a quiz!",
            blocks=blocks
        )
        print(f"Message sent to user {user_id}, ts: {response['ts']}")
    except SlackApiError as e:
        print(f"Error sending message to user {user_id}: {e.response['error']}")

def send_message_to_user(client, user_id, message_text):
    """Helper function to send a message to a user."""
    try:
        response = client.conversations_open(users=[user_id])
        channel_id = response["channel"]["id"]

        client.chat_postMessage(
            channel=channel_id,
            text=message_text
        )
    except SlackApiError as e:
        print(f"Error sending message to user {user_id}: {e.response['error']}")


def handle_quiz_response(user_id, selected_user_id, payload, team_id):
    """Handles the user's quiz response, updates scores, and modifies the Slack message to reflect the answer."""
    # Set up the Slack client with the correct access token
    client = get_slack_client(team_id)

    # Fetch the user's active quiz session
    quiz_session = get_active_quiz_session(user_id)
    if not quiz_session or not quiz_session.correct_user_id:
        try:
            client.chat_postMessage(channel=user_id, text="Sorry, your quiz session has expired.")
        except SlackApiError as e:
            print(f"Error sending expired session message to user {user_id}: {e.response['error']}")
        return

    correct_user_id = quiz_session.correct_user_id

    # Determine if the user's selection is correct
    is_correct = selected_user_id == correct_user_id

    # Update the user's score if correct
    if is_correct:
        update_score(user_id, points=1)

    # Prepare to update the original message
    original_blocks = payload['message']['blocks']
    action_id = payload['actions'][0]['action_id']
    selected_option_index = int(action_id.split('_')[-1])

    # Find the action block containing the answer buttons
    answer_action_block = next(
        (block for block in original_blocks if block.get('block_id') == 'answer_buttons'),
        None
    )

    if not answer_action_block:
        print("Answer action block not found.")
        return

    # Modify the action block to reflect correct and incorrect choices
    for idx, element in enumerate(answer_action_block['elements']):
        # Assign a new action_id to disable further interaction
        element['action_id'] = f"disabled_{idx}"
        element['text']['emoji'] = True  # Ensure 'emoji' field is set

        # Style the buttons based on correctness
        if element['value'] == correct_user_id:
            element['style'] = 'primary'  # Correct answer in green
        elif element['value'] == selected_user_id:
            element['style'] = 'danger'   # User's incorrect selection in red
        else:
            element.pop('style', None)    # Remove 'style' if any

    # Add feedback text at the top
    if is_correct:
        feedback_text = "🎉 Correct! You really know your colleagues!"
    else:
        correct_name = get_user_name(correct_user_id)
        feedback_text = f"❌ Nope! This is your amazing colleague called *{correct_name}*."

    # Insert feedback text at the top of the blocks
    original_blocks.insert(0, {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": feedback_text
        }
    })

    # Extract channel ID and message timestamp from payload
    channel_id = payload['channel']['id']
    message_ts = payload['message']['ts']

    # Update the original message with feedback and disabled buttons
    try:
        client.chat_update(
            channel=channel_id,
            ts=message_ts,
            blocks=original_blocks,
            text=feedback_text
        )
    except SlackApiError as e:
        print(f"Error updating message: {e.response['error']}")

    # Remove the stored answer (delete the quiz session)
    delete_quiz_session(user_id)