# app.py
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import json
from models import db, User, Score
app = Flask(__name__)

# Configuration for SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///facesinq.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

#db = SQLAlchemy(app)
db.init_app(app)

# Import the rest of your modules
from db import init_db, migrate_db
from utils import fetch_and_store_users
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier
from quiz_app import send_quiz_to_user
from leaderboard import send_leaderboard


import sqlite3

with app.app_context():
    db.create_all()  # Create tables if they don't exist
# Initialize the existing database (not needed once you fully migrate to SQLAlchemy)
#init_db()
#migrate_db()
fetch_and_store_users()




def update_user_opt_in(user_id, opt_in):
    user = User.query.get(user_id)
    if user:
        user.opted_in = opt_in
        db.session.commit()

def has_user_opted_in(user_id):
    conn = sqlite3.connect('facesinq.db')
    c = conn.cursor()
    c.execute('SELECT opted_in FROM users WHERE id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result is not None and result[0] == 1

def update_score(user_id, points):
    conn = sqlite3.connect('facesinq.db')
    c = conn.cursor()
    # Check if the user already has a score entry
    c.execute('SELECT score FROM scores WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    if result:
        # Update the existing score
        new_score = result[0] + points
        c.execute('UPDATE scores SET score = ? WHERE user_id = ?', (new_score, user_id))
    else:
        # Insert a new score entry
        c.execute('INSERT INTO scores (user_id, score) VALUES (?, ?)', (user_id, points))
    conn.commit()
    conn.close()

def get_user_score(user_id):
    conn = sqlite3.connect('facesinq.db')
    c = conn.cursor()
    c.execute('SELECT score FROM scores WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def get_opted_in_user_count():
    conn = sqlite3.connect('facesinq.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users WHERE opted_in = 1')
    count = c.fetchone()[0]
    conn.close()
    return count


@app.route('/')
def index():
    return 'FaceSinq is running!'

@app.route('/slack/actions', methods=['POST'])
def slack_actions():
    # Verify the request signature
    SLACK_SIGNING_SECRET = os.environ.get('SLACK_SIGNING_SECRET')
    signature_verifier = SignatureVerifier(signing_secret=SLACK_SIGNING_SECRET)
    SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
    client = WebClient(token=SLACK_BOT_TOKEN)

    if not signature_verifier.is_valid_request(request.get_data(), request.headers):
        return jsonify({'error': 'invalid request signature'}), 403

    payload = json.loads(request.form.get('payload'))
    action = payload['actions'][0]
    action_id = action['action_id']
    user_id = payload['user']['id']
    selected_user_id = action['value']
    message_ts = payload['message']['ts']
    channel_id = payload['channel']['id']

    if action_id.startswith('quiz_response_'):
        # Retrieve correct answer from database
        conn = sqlite3.connect('facesinq.db')
        c = conn.cursor()
        c.execute('SELECT correct_user_id FROM quiz_sessions WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        if not result or not result[0]:
            conn.close()
            client.chat_postMessage(channel=user_id, text="Sorry, your quiz session has expired.")
            return '', 200

        correct_user_id = result[0]
        conn.close()

        # Determine if the user's selection is correct
        is_correct = selected_user_id == correct_user_id

        # Update the user's score if correct
        if is_correct:
            update_score(user_id, 1)

        # Prepare to update the original message
        original_blocks = payload['message']['blocks']
        selected_option_index = int(action_id.split('_')[-1])

        # Find the action block containing the answer buttons
        answer_action_block = None
        for block in original_blocks:
            if block.get('block_id') == 'answer_buttons':
                answer_action_block = block
                break

        if not answer_action_block:
            print("Answer action block not found.")
            return '', 200

        # Modify the action block to reflect correct and incorrect choices
        for idx, element in enumerate(answer_action_block['elements']):
            # Assign a new action_id to disable further interaction
            element['action_id'] = f"disabled_{idx}"  # Set a unique action_id
            element['text']['emoji'] = True  # Ensure 'emoji' field is set

            # Style the buttons based on correctness
            if element['value'] == correct_user_id:
                element['style'] = 'primary'  # Correct answer in green
            elif element['value'] == selected_user_id:
                element['style'] = 'danger'   # User's incorrect selection in red
            else:
                element.pop('style', None)    # Remove 'style' if any
        #print(f"Updating message with blocks: {json.dumps(original_blocks, indent=2)}")


        # Add feedback text at the top
        if is_correct:
            feedback_text = "🎉 Correct! You really know your colleagues!"
        else:
            # Get the name of the correct colleague
            conn = sqlite3.connect('facesinq.db')
            c = conn.cursor()
            c.execute('SELECT name FROM users WHERE id = ?', (correct_user_id,))
            correct_name_result = c.fetchone()
            conn.close()
            correct_name = correct_name_result[0] if correct_name_result else "Unknown"
            feedback_text = f"❌ Nope! This is your amazing colleague called *{correct_name}*."

        # Insert feedback text at the top of the blocks
        original_blocks.insert(0, {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": feedback_text
            }
        })
        #print(f"Updating message with blocks: {json.dumps(original_blocks, indent=2)}")
        # Update the original message
        try:
            client.chat_update(
                channel=channel_id,
                ts=message_ts,
                blocks=original_blocks,
                text=feedback_text  # Add this line
            )
        except SlackApiError as e:
            print(f"Error updating message: {e.response['error']}")

        # Remove the stored answer
        conn = sqlite3.connect('facesinq.db')
        c = conn.cursor()
        c.execute('DELETE FROM quiz_sessions WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()

    elif action_id == 'next_quiz':
        # Handle the "Next Quiz" button click
        send_quiz_to_user(user_id)

        # Modify the original message to disable the "Next Quiz" button
        original_blocks = payload['message']['blocks']

        # Find the action block containing the "Next Quiz" button
        next_quiz_block = None
        for block in original_blocks:
            if block.get('block_id') == 'next_quiz_block':
                next_quiz_block = block
                break

        if next_quiz_block:
            for element in next_quiz_block['elements']:
                if element.get('action_id') == 'next_quiz':
                    element['action_id'] = 'disabled_next_quiz'
                    element['text']['text'] = "Next Quiz Sent"
                    element['style'] = 'primary'
                    break
        else:
            print("Next Quiz action block not found.")


        # Update the message
        try:
            client.chat_update(
                channel=channel_id,
                ts=message_ts,
                blocks=original_blocks,
                text="Here's your next quiz!"
            )
        except SlackApiError as e:
            print(f"Error updating message: {e.response['error']}")

    else:
        # Handle other actions if any
        pass

    return '', 200


@app.route('/slack/commands', methods=['POST'])
def slack_commands():
    # Read environment variables inside the function
    SLACK_SIGNING_SECRET = os.environ.get('SLACK_SIGNING_SECRET')
    signature_verifier = SignatureVerifier(signing_secret=SLACK_SIGNING_SECRET)
    SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
    client = WebClient(token=SLACK_BOT_TOKEN)

    # Verify the request signature
    if not signature_verifier.is_valid_request(request.get_data(), request.headers):
        return jsonify({'error': 'invalid request signature'}), 403

    command = request.form.get('command')
    user_id = request.form.get('user_id')
    text = request.form.get('text').strip().lower()

    if command == '/facesinq':
        if text == 'opt-in':
            update_opt_in_status(user_id, True)
            return jsonify(response_type='ephemeral', text='You have opted in to FaceSinq quizzes!'), 200
        elif text == 'opt-out':
            update_opt_in_status(user_id, False)
            return jsonify(response_type='ephemeral', text='You have opted out of FaceSinq quizzes.'), 200
        elif text == 'quiz':
            # Check if the user has opted in
            if not has_user_opted_in(user_id):
                return jsonify(response_type='ephemeral', text='You need to opt-in first using `/facesinq opt-in`.'), 200
            # Send a quiz to the user
            send_quiz_to_user(user_id)
            return jsonify(response_type='ephemeral', text='Quiz sent!'), 200
        elif text == 'stats':
            # Handle the stats command (we'll implement this in the next section)
            count = get_opted_in_user_count()
            return jsonify(response_type='ephemeral', text=f'There are {count} users opted in to FaceSinq quizzes.'), 200
        elif text == 'score':
            score = get_user_score(user_id)
            return jsonify(response_type='ephemeral', text=f'Your current score is {score}.'), 200
        elif text == 'leaderboard':
            score = send_leaderboard(user_id)

    else:
            return jsonify(response_type='ephemeral', text="Usage: /facesinq [opt-in | opt-out | quiz | stats]"), 200

    return '', 404


@app.route('/slack/events', methods=['POST'])
def slack_events():
    # Get the request body and headers
    body = request.get_data()
    headers = request.headers
    # Read environment variables inside the function
    SLACK_SIGNING_SECRET = os.environ.get('SLACK_SIGNING_SECRET')
    signature_verifier = SignatureVerifier(signing_secret=SLACK_SIGNING_SECRET)
    SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
    client = WebClient(token=SLACK_BOT_TOKEN)

    # Parse the request body as JSON
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        data = {}

    # Handle URL verification challenge
    if data.get('type') == 'url_verification':
        challenge = data.get('challenge')
        return jsonify({'challenge': challenge}), 200

    # Verify the request signature
    if not signature_verifier.is_valid_request(body, headers):
        return jsonify({'error': 'invalid request signature'}), 403

    # Handle event callbacks
    if data.get('type') == 'event_callback':
        event = data.get('event')
        # You can handle different event types here
        return '', 200

    # If the request doesn't match any known types
    return '', 404

if __name__ == '__main__':

    from db import init_db, migrate_db
    from utils import fetch_and_store_users
    from quiz_app import send_quiz
    from apscheduler.schedulers.background import BackgroundScheduler
    with app.app_context():
        db.create_all()  # Create tables if they don't exist
    #init_db()
    #migrate_db()
    fetch_and_store_users()

    # Schedule the quiz
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_quiz, 'interval', minutes=60)  # Adjust frequency
    #scheduler.add_job(send_leaderboard, 'cron', day_of_week='fri', hour=17)  # Adjust timing as needed
    scheduler.start()

    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
