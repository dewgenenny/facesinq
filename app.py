from flask import Flask, request, jsonify
import sqlite3
import json
import os
from slack_sdk import WebClient
from slack_sdk.signature import SignatureVerifier

app = Flask(__name__)

SLACK_SIGNING_SECRET = os.environ.get('SLACK_SIGNING_SECRET')
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN')
client = WebClient(token=SLACK_BOT_TOKEN)
signature_verifier = SignatureVerifier(SLACK_SIGNING_SECRET)

@app.route('/slack/events', methods=['POST'])
def slack_events():
    if not signature_verifier.is_valid_request(request.get_data(), request.headers):
        return jsonify({'error': 'invalid request'}), 403

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

if __name__ == '__main__':
    from db import init_db
    from utils import fetch_and_store_users
    from quiz_app import send_quiz
    from apscheduler.schedulers.background import BackgroundScheduler

    init_db()
    fetch_and_store_users()

    # Schedule the quiz
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_quiz, 'interval', minutes=60)  # Adjust frequency
    scheduler.start()

    from leaderboard import send_leaderboard
    scheduler.add_job(send_leaderboard, 'cron', day_of_week='fri', hour=17)  # Adjust timing as needed

    app.run(host='0.0.0.0', port=3000)
