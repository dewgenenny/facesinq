from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import random
import sqlite3
import os


# Define quiz_answers at the module level
quiz_answers = {}

def send_quiz_to_user(user_id):
    global quiz_answers

    SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
    client = WebClient(token=SLACK_BOT_TOKEN)

    conn = sqlite3.connect('facesinq.db')
    c = conn.cursor()

    # Exclude the user themselves
    c.execute('SELECT id, name, image FROM users WHERE id != ? AND opted_in = 1', (user_id,))
    colleagues = c.fetchall()
    if len(colleagues) < 4:
        conn.close()
        return

    correct_choice = random.choice(colleagues)
    options = [correct_choice] + random.sample(
        [col for col in colleagues if col != correct_choice], 3
    )
    random.shuffle(options)

    # Store the correct answer
    quiz_answers[user_id] = correct_choice[0]

    # Build interactive message
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Who's this colleague?*"
            },
            "accessory": {
                "type": "image",
                "image_url": correct_choice[2] or "https://via.placeholder.com/150",
                "alt_text": "Colleague's image"
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": option[1]},
                    "value": option[0],
                    "action_id": "quiz_response"
                } for option in options
            ]
        }
    ]

    try:
        client.chat_postMessage(
            channel=user_id,
            text="Time for a quiz!",
            blocks=blocks
        )
    except SlackApiError as e:
        print(f"Error sending message to {user_id}: {e.response['error']}")
    conn.close()

def send_quiz():
    global quiz_answers
    SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
    client = WebClient(token=SLACK_BOT_TOKEN)
    conn = sqlite3.connect('facesinq.db')
    c = conn.cursor()
    # Select users who have opted in
    c.execute('SELECT id FROM users WHERE opted_in = 1')
    user_ids = [row[0] for row in c.fetchall()]

    for user_id in user_ids:
        # Exclude the user themselves
        c.execute('SELECT id, name, image FROM users WHERE id != ? AND opted_in = 1', (user_id,))
        colleagues = c.fetchall()
        if len(colleagues) < 4:
            continue

        correct_choice = random.choice(colleagues)
        options = [correct_choice] + random.sample(
            [col for col in colleagues if col != correct_choice], 3
        )
        random.shuffle(options)

        # Store the correct answer
        quiz_answers[user_id] = correct_choice[0]

        # Build interactive message
        # Include the colleague's image
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Who's this colleague?*"
                },
                "accessory": {
                    "type": "image",
                    "image_url": correct_choice[2] or "https://via.placeholder.com/150",
                    "alt_text": "Colleague's image"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": option[1]},
                        "value": option[0],
                        "action_id": "quiz_response"
                    } for option in options
                ]
            }
        ]

        try:
            client.chat_postMessage(
                channel=user_id,
                text="Time for a quiz!",
                blocks=blocks
            )
        except SlackApiError as e:
            print(f"Error sending message to {user_id}: {e.response['error']}")
    conn.close()
