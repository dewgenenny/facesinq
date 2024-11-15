from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import random
import sqlite3
import os

SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
client = WebClient(token=SLACK_BOT_TOKEN)

# Define quiz_answers at the module level
quiz_answers = {}

def send_quiz():
    global quiz_answers  # Declare as global to modify the module-level variable

    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    c.execute('SELECT id FROM users')
    user_ids = [row[0] for row in c.fetchall()]

    for user_id in user_ids:
        # Exclude the user themselves
        c.execute('SELECT id, name FROM users WHERE id != ?', (user_id,))
        colleagues = c.fetchall()
        if len(colleagues) < 4:
            continue

        correct_choice = random.choice(colleagues)
        options = [correct_choice] + random.sample(
            [col for col in colleagues if col != correct_choice], 3
        )
        random.shuffle(options)

        # Store the correct answer temporarily
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
                    "image_url": "https://via.placeholder.com/150",  # Replace with actual image if available
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
