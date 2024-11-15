from flask import Flask, request, jsonify
import sqlite3
import json
import os
from slack_sdk import WebClient
from slack_sdk.signature import SignatureVerifier

app = Flask(__name__)

#SLACK_SIGNING_SECRET = os.environ.get('SLACK_SIGNING_SECRET')
#signature_verifier = SignatureVerifier(SLACK_SIGNING_SECRET)

# Import quiz_answers from quiz_app
from quiz_app import quiz_answers, send_quiz_to_user
from leaderboard import send_leaderboard  # Import send_leaderboard


def update_opt_in_status(user_id, opt_in):
    conn = sqlite3.connect('facesinq.db')
    c = conn.cursor()
    opted_in_value = 1 if opt_in else 0

    # Update the user's opt-in status
    c.execute('UPDATE users SET opted_in = ? WHERE id = ?', (opted_in_value, user_id))
    conn.commit()
    conn.close()

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

    # Check if action_id starts with 'quiz_response_'
    if action_id.startswith('quiz_response_'):
        # Handle the quiz response
        correct_user_id = quiz_answers.get(user_id)
        if not correct_user_id:
            # No quiz answer stored
            return '', 200

        if selected_user_id == correct_user_id:
            # Correct answer
            client.chat_postMessage(channel=user_id, text="🎉 Correct!")
            update_score(user_id, 1)
        else:
            # Incorrect answer
            client.chat_postMessage(channel=user_id, text="❌ Incorrect.")
        # Remove the stored answer
        del quiz_answers[user_id]
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
    signature_verifier = SignatureVerifier(SLACK_SIGNING_SECRET)
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

    # Handle interactive message payloads
    if 'payload' in request.form:
        payload = json.loads(request.form['payload'])
        user_id = payload['user']['id']
        action = payload['actions'][0]
        selected_user_id = action['value']

        # Retrieve the correct answer
        correct_user_id = quiz_answers.get(user_id)

        conn = sqlite3.connect('quiz.db')
        c = conn.cursor()

        if not correct_user_id:
            message = "Sorry, your quiz session has expired."
        elif selected_user_id == correct_user_id:
            # Update score
            c.execute('INSERT OR IGNORE INTO scores (user_id, score) VALUES (?, 0)', (user_id,))
            c.execute('UPDATE scores SET score = score + 1 WHERE user_id = ?', (user_id,))
            conn.commit()
            message = "🎉 Correct!"
        else:
            message = "❌ Incorrect."

        # Clean up
        quiz_answers.pop(user_id, None)
        conn.close()

        client.chat_postMessage(channel=user_id, text=message)
        return '', 200

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

    init_db()
    migrate_db()
    fetch_and_store_users()

    # Schedule the quiz
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_quiz, 'interval', minutes=60)  # Adjust frequency
    scheduler.add_job(send_leaderboard, 'cron', day_of_week='fri', hour=17)  # Adjust timing as needed
    scheduler.start()

    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
