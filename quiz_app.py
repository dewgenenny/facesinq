from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import random
import sqlite3
import os


# Define quiz_answers at the module level
quiz_answers = {}

# quiz_app.py

def send_quiz_to_user(user_id):
    global quiz_answers

    SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
    client = WebClient(token=SLACK_BOT_TOKEN)

    conn = sqlite3.connect('facesinq.db')
    c = conn.cursor()

    # Get all colleagues (excluding the user themselves)
    c.execute('SELECT id, name, image FROM users WHERE id != ?', (user_id,))
    colleagues = c.fetchall()

    if len(colleagues) < 4:
        print(f"Not enough colleagues to send a quiz to user {user_id}")
        conn.close()
        return

    correct_choice = random.choice(colleagues)
    options = [correct_choice] + random.sample(
        [col for col in colleagues if col != correct_choice], 3
    )
    random.shuffle(options)

    # Store the correct answer
    conn.execute('REPLACE INTO quiz_sessions (user_id, correct_user_id) VALUES (?, ?)', (user_id, correct_choice[0]))
    conn.commit()
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
            "image_url": correct_choice[2] or "https://via.placeholder.com/600",
            "alt_text": "Image of a colleague"
        },
        # Action buttons
        {
            "type": "actions",
            "elements": []
        }
    ]

    # Populate the actions block with options, ensuring unique action_ids
    for idx, option in enumerate(options):
        blocks[2]["elements"].append({
            "type": "button",
            "text": {"type": "plain_text", "text": option[1]},
            "value": option[0],
            "action_id": f"quiz_response_{idx}"
        })

    # Debugging: Print the blocks payload
    print(f"Sending the following blocks payload: {blocks}")

    try:
        response = client.chat_postMessage(
            channel=user_id,
            text="Time for a quiz!",
            blocks=blocks
        )
        print(f"Message sent to user {user_id}, ts: {response['ts']}")
    except SlackApiError as e:
        print(f"Error sending message to {user_id}: {e.response['error']}")
    conn.close()



# quiz_app.py

# quiz_app.py

def send_quiz():
    global quiz_answers

    SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
    client = WebClient(token=SLACK_BOT_TOKEN)

    conn = sqlite3.connect('facesinq.db')
    c = conn.cursor()
    # Select users who have opted in to receive quizzes
    c.execute('SELECT id FROM users WHERE opted_in = 1')
    recipient_ids = [row[0] for row in c.fetchall()]

    # Get all colleagues (regardless of opt-in status)
    c.execute('SELECT id, name, image FROM users')
    all_colleagues = c.fetchall()

    for user_id in recipient_ids:
        # Exclude the user themselves from options
        colleagues = [colleague for colleague in all_colleagues if colleague[0] != user_id]
        if len(colleagues) < 4:
            print(f"Not enough colleagues to send a quiz to user {user_id}")
            continue

        correct_choice = random.choice(colleagues)
        options = [correct_choice] + random.sample(
            [col for col in colleagues if col != correct_choice], 3
        )
        random.shuffle(options)

        # Store the correct answer
        quiz_answers[user_id] = correct_choice[0]

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
                "image_url": correct_choice[2] or "https://via.placeholder.com/600",
                "alt_text": "Image of a colleague"
            },
            # Action buttons
            {
                "type": "actions",
                "elements": []
            }
        ]

        # Populate the actions block with options, ensuring unique action_ids
        for idx, option in enumerate(options):
            blocks[2]["elements"].append({
                "type": "button",
                "text": {"type": "plain_text", "text": option[1]},
                "value": option[0],
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
    conn.close()

