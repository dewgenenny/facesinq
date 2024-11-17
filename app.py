# app.py
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import json
from db import engine, Session, initialize_database  # Import the engine and initialization function
from models import User, Score, QuizSession , Base # Ensure models are imported so they are registered
from database_helpers import get_user, update_score, update_user_opt_in, get_user_score, get_opted_in_user_count, has_user_opted_in, get_user_name
app = Flask(__name__)

# Configuration for SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///facesinq.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

#db = SQLAlchemy(app)
#db.init_app(app)

# Import the rest of your modules
#from db import init_db, migrate_db
from utils import fetch_and_store_users
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier
from quiz_app import send_quiz_to_user
from leaderboard import send_leaderboard
from slack_client import get_slack_client, verify_slack_signature

import sqlite3

with app.app_context():
    Base.metadata.create_all(bind=engine)  # Create all tables associated with the Base metadata
    initialize_database()  # Optional: add initial setup logic if needed
    fetch_and_store_users()

# Initialize the existing database (not needed once you fully migrate to SQLAlchemy)
#init_db()
#migrate_db()



@app.route('/')
def index():
    return 'FaceSinq is running!'

@app.route('/slack/actions', methods=['POST'])
def slack_actions():
    # initialise slack client
    client = get_slack_client()

    # verify signature
    if not verify_slack_signature(request):
        return jsonify({'error': 'invalid request signature'}), 403

    # Parse the payload
    payload = json.loads(request.form.get('payload'))
    action = payload['actions'][0]
    action_id = action['action_id']
    user_id = payload['user']['id']
    selected_user_id = action['value']
    message_ts = payload['message']['ts']
    channel_id = payload['channel']['id']

    if action_id.startswith('quiz_response_'):
        # Fetch the current quiz session
        with Session() as session:
            quiz_session = session.query(QuizSession).filter_by(user_id=user_id).one_or_none()

            if not quiz_session or not quiz_session.correct_user_id:
                client.chat_postMessage(channel=user_id, text="Sorry, your quiz session has expired.")
                return '', 200

            correct_user_id = quiz_session.correct_user_id

            # Determine if the user's selection is correct
            is_correct = selected_user_id == correct_user_id

            # Update the user's score if correct
            if is_correct:
                update_score(user_id, 1)

            # Prepare to update the original message
            original_blocks = payload['message']['blocks']
            selected_option_index = int(action_id.split('_')[-1])

            # Find the action block containing the answer buttons
            answer_action_block = next(
                (block for block in original_blocks if block.get('block_id') == 'answer_buttons'),
                None
            )

            if not answer_action_block:
                print("Answer action block not found.")
                return '', 200

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
            session.query(QuizSession).filter_by(user_id=user_id).delete()
            session.commit()
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
        return '', 200
    return '', 200
@app.route('/slack/commands', methods=['POST'])
def slack_commands():

    # Verify the request signature
    if not verify_slack_signature(request):
        return jsonify({'error': 'invalid request signature'}), 403


    command = request.form.get('command')
    user_id = request.form.get('user_id')
    text = request.form.get('text').strip().lower()
    channel_id = request.form.get('channel_id')  # Extract channel_id from the incoming Slack command

    if command == '/facesinq':
        if text == 'opt-in':
            update_user_opt_in(user_id, True)
            return jsonify(response_type='ephemeral', text='You have opted in to FaceSinq quizzes!'), 200
        elif text == 'opt-out':
            update_user_opt_in(user_id, False)
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
            print("Got leaderboard request")
            send_leaderboard(channel_id)
            #return jsonify(response_type='ephemeral', text=f'Leaderboard sent'), 200
            return 200

    else:
            return jsonify(response_type='ephemeral', text="Usage: /facesinq [opt-in | opt-out | quiz | stats]"), 200

    return '', 404


@app.route('/slack/events', methods=['POST'])
def slack_events():
    # Get the request body and headers
    body = request.get_data()
    headers = request.headers

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
    if not verify_slack_signature(request):
        return jsonify({'error': 'invalid request signature'}), 403

    # Handle event callbacks
    if data.get('type') == 'event_callback':
        event = data.get('event')
        # You can handle different event types here
        return '', 200

    # If the request doesn't match any known types
    return '', 404

if __name__ == '__main__':

    from utils import fetch_and_store_users
    from quiz_app import send_quiz
    from apscheduler.schedulers.background import BackgroundScheduler
    with app.app_context():
        Base.metadata.create_all(bind=engine)  # Create all tables associated with the Base metadata

    fetch_and_store_users()

    # Schedule the quiz
    scheduler = BackgroundScheduler()
    #scheduler.add_job(send_quiz, 'interval', minutes=60)  # Adjust frequency
    #scheduler.add_job(send_leaderboard, 'cron', day_of_week='fri', hour=17)  # Adjust timing as needed
    scheduler.add_job(fetch_and_store_users, 'interval', hours=2, kwargs={'update_existing': True})
    scheduler.start()

    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
