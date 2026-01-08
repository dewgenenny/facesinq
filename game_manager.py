# game_manager.py
import random
from slack_client import get_slack_client
from database_helpers import create_or_update_quiz_session, get_colleagues_excluding_user, update_score, get_active_quiz_session, get_user_name, delete_quiz_session, get_user
from slack_sdk.errors import SlackApiError
from models import User
import logging
from image_utils import generate_grid_image_bytes

import threading

import time

logger = logging.getLogger(__name__)

# Cache to store pre-generated quizzes: {user_id: quiz_data}
# quiz_data = {
#   'correct_choice': User object,
#   'options': [User objects,...],
#   'uploaded_file_id': str (optional),
#   'difficulty': str
# }
PENDING_QUIZZES = {}

def generate_quiz_data(user_id, team_id):
    """
    Generates the data structure required for a quiz (options, grid, etc.),
    without sending it or updating the database yet.
    """
    # Get user difficulty mode
    user = get_user(user_id)
    if not user:
        return None
        
    difficulty = getattr(user, 'difficulty_mode', 'easy')

    # Get all colleagues, excluding the user themselves
    colleagues = get_colleagues_excluding_user(user_id, team_id)
    
    # Check if there are enough colleagues for a quiz
    if len(colleagues) < 4:
        logger.warning(f"Not enough colleagues to generate a quiz for user {user_id}. Found {len(colleagues)}.")
        return None

    # Select correct answer and random options
    correct_choice = random.choice(colleagues)
    options = [correct_choice] + random.sample(
        [col for col in colleagues if col != correct_choice], 3
    )
    random.shuffle(options)
    
    # Pre-generate grids for Hard Mode (Bytes only)
    grid_bytes = None
    if difficulty == 'hard':
        # Hard Mode: Pre-generate the grid
        image_urls = [opt.image for opt in options]
        grid_bytes = generate_grid_image_bytes(image_urls)

    return {
        'correct_choice': correct_choice,
        'options': options,
        'uploaded_file_id': None,
        'uploaded_file_url': None,
        'grid_bytes': grid_bytes,
        'difficulty': difficulty
    }

def prepare_next_quiz(user_id, team_id):
    """Background task to generate the next quiz and store it in cache."""
    try:
        logger.info(f"Preparing next quiz for user {user_id}...")
        quiz_data = generate_quiz_data(user_id, team_id)
        if quiz_data:
            PENDING_QUIZZES[user_id] = quiz_data
            logger.info(f"Next quiz prepared and cached for user {user_id}.")
        else:
            logger.warning(f"Failed to prepare next quiz for {user_id} (insufficient data?)")
    except Exception as e:
        logger.error(f"Error preparing next quiz for {user_id}: {e}")

def send_quiz_to_user(user_id, team_id):
    """Send a quiz to a specific user, using cached data if available."""
    # Set up the Slack client
    client = get_slack_client(team_id)

    # Check if the user already has an active quiz session
    # Note: If we just finished a quiz, the session should be gone by now.
    existing_quiz = get_active_quiz_session(user_id)
    if existing_quiz:
        logger.info(f"User {user_id} already has an active quiz.")
        send_message_to_user(client, user_id, "You already have an active quiz! Please answer it before requesting a new one.")
        return False, "You already have an active quiz!"

    # 1. Retrieve or Generate Quiz Data
    quiz_data = PENDING_QUIZZES.pop(user_id, None)
    
    if quiz_data:
        logger.info(f"Using cached quiz for user {user_id}!")
    else:
        logger.info(f"No cached quiz for user {user_id}. Generating on the fly...")
        quiz_data = generate_quiz_data(user_id, team_id)
        
    if not quiz_data:
        send_message_to_user(client, user_id, "Not enough colleagues to generate a quiz yet!")
        return False, "Not enough colleagues."

    # Unpack data
    correct_choice = quiz_data['correct_choice']
    options = quiz_data['options']
    grid_bytes = quiz_data.get('grid_bytes') # Bytes for 2x2 grid
    difficulty = quiz_data['difficulty']

    # 2. Store session in DB
    create_or_update_quiz_session(user_id=user_id, correct_user_id=correct_choice.id)

    # 3. Construct Wrapper Blocks (Question + Buttons)
    # Note: For Hard Mode, the Image Grid is sent as a separate file upload message!
    if difficulty == 'hard':
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🧠 *Hard Mode*\nWho is *{correct_choice.name}*? 👇 (See image above)"
                }
            }
        ]
        
        # Buttons
        button_elements = []
        for idx, option in enumerate(options):
            button_elements.append({
                "type": "button",
                "text": {"type": "plain_text", "text": f"Option {idx + 1}"},
                "value": option.id,
                "action_id": f"quiz_response_{idx}"
            })
            
        blocks.append({
            "type": "actions",
            "block_id": "answer_buttons",
            "elements": button_elements
        })

    else:
        # EASY MODE
        # Safety check for image
        image_url = correct_choice.image if correct_choice.image else "https://via.placeholder.com/150?text=No+Image"
        
        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "🤔 *Who is this colleague?*"}
            },
            {
                "type": "image",
                "image_url": image_url,
                "alt_text": "Image of a colleague"
            },
            {
                "type": "actions",
                "block_id": "answer_buttons",
                "elements": []
            }
        ]
        for idx, option in enumerate(options):
            # Safety check for name
            btn_text = option.name if option.name else f"Option {idx+1}"
            blocks[2]["elements"].append({
                "type": "button",
                "text": {"type": "plain_text", "text": btn_text},
                "value": option.id,
                "action_id": f"quiz_response_{idx}"
            })

    # Note: We do NOT adding the 'Next Quiz' button yet. It appears after answering.

    # 4. Send Message (Upload + Blocks)
    try:
        # Open DM Channel
        resp = client.conversations_open(users=[user_id])
        channel_id = resp["channel"]["id"]
        
        # If Hard Mode and we have bytes, upload directly to the channel
        if difficulty == 'hard' and grid_bytes:
            try:
                logger.info(f"Uploading 2x2 grid directly to channel {channel_id}...")
                client.files_upload_v2(
                    channel=channel_id, # Post directly to channel
                    file=grid_bytes,
                    filename="quiz_2x2.jpg",
                    title="Who is this?",
                    initial_comment="🧠 *Hard Mode Grid*" # Optional context
                )
                time.sleep(2) # Ensure image appears before blocks
            except SlackApiError as e:
                logger.error(f"Failed to upload grid image: {e}")
                # We continue to send the blocks, user will see error there or missing image.
                # Maybe fallback blocks? 
                pass
            except Exception as e:
                logger.error(f"Unexpected error uploading grid image: {e}")
                pass

        import json
        logger.info(f"Sending quiz blocks: {json.dumps(blocks)}")
        
        response = client.chat_postMessage(channel=channel_id, text="Time for a quiz!", blocks=blocks)
        logger.info(f"Quiz sent to user {user_id}, ts: {response['ts']}")
        
        # 5. TRIGGER BACKGROUND PREPARATION FOR NEXT QUIZ
        threading.Thread(target=prepare_next_quiz, args=(user_id, team_id)).start()
        
        return True, "Quiz sent!"

    except Exception as e:
        logger.error(f"Error sending quiz to {user_id}: {e}")
        # CRITICAL: Clean up the session if sending failed so user isn't stuck
        delete_quiz_session(user_id)
        return False, str(e)
    except SlackApiError as e:
        logger.error(f"Error sending quiz to {user_id}: {e.response['error']}")
        delete_quiz_session(user_id) # Ensure cleanup here too
        return False, f"Error: {e.response['error']}"

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

    try:
        # Determine if the user's selection is correct
        is_correct = selected_user_id == correct_user_id

        # Calculate points and streak
        from datetime import datetime, timedelta
        from database_helpers import get_user, update_user_streak

        user = get_user(user_id)
        now = datetime.utcnow()
        
        current_streak = user.current_streak if user.current_streak else 0
        last_answered = user.last_answered_at
        
        new_streak = current_streak
        
        # Check streak logic
        if last_answered:
            # Check if last answered was yesterday (or today)
            # Using simple day difference for now
            last_date = last_answered.date()
            today_date = now.date()
            
            if last_date == today_date:
                 # Already answered today, keep streak
                 pass
            elif last_date == today_date - timedelta(days=1):
                 # Answered yesterday, increment streak
                 new_streak += 1
            else:
                 # Missed a day or more, reset streak
                 new_streak = 1
        else:
            # First time playing
            new_streak = 1
            
        # Cap streak bonus at 10 days (50 points)
        streak_bonus_multiplier = min(new_streak, 10)
        streak_points = streak_bonus_multiplier * 5
        
        if is_correct:
            base_points = 10
            total_points = base_points + streak_points
        else:
            base_points = 2
            total_points = base_points # No streak bonus for wrong answers, or maybe yes? Plan said: "+5 points per day of streak". 
            # Plan example: "Day 1 = 10 pts. Day 2 = 10 + 5 = 15 pts." implying bonus is added to correct answer.
            # Let's assume streak bonus is only for correct answers to prevent farming points with wrong answers?
            # Actually, "Participation Points: Users get points even if they answer incorrectly".
            # Let's give base participation points (2) for incorrect, but maybe NO streak bonus?
            # "Streak System: Rewards users for playing on consecutive days."
            # If I get it wrong, do I keep my streak? Most games say yes if you play.
            # So I should update the streak regardless of correctness?
            # Plan says: "Verify DB last_answered_at is updated and current_streak becomes 1."
            # It doesn't explicitly say if wrong answer updates streak.
            # Usually, just *playing* maintains the streak.
            # But *points* for streak usually go on top of *winning*.
            # Let's implement: Streak increments if you PLAY. Bonus points only if you WIN.
            # Wait, if I answer wrong, do I get streak bonus points? 
            # "Day 1 = 10 pts." -> Correct answer.
            # Let's stick to simple: Streak Bonus only on Correct Answer.
            # But playing (even wrong) maintains/increments streak count.
            
            total_points = base_points

        # Update streak in DB
        update_user_streak(user_id, new_streak, now)

        # Update the user's score and attempts
        update_score(user_id, total_points, is_correct=is_correct)

        # Prepare to update the original message
        original_blocks = payload['message']['blocks']
        action_id = payload['actions'][0]['action_id']
        selected_option_index = int(action_id.split('_')[-1])

        # Iterate through all blocks to find and update ALL answer buttons
        # This handles both the "grouped" layout (block_id='answer_buttons') and the "interleaved" layout (multiple action blocks)
        answer_blocks_found = False
        
        for block in original_blocks:
            if block.get('type') == 'actions':
                elements = block.get('elements', [])
                # Check if this block contains quiz response buttons
                # We match if ANY element in the block has an action_id starting with 'quiz_response_'
                if any(el.get('action_id', '').startswith('quiz_response_') for el in elements):
                    answer_blocks_found = True
                    
                    for idx, element in enumerate(elements):
                        # Only modify buttons that are part of the quiz (safety check)
                        if element.get('action_id', '').startswith('quiz_response_'):
                            # Assign a new action_id to disable further interaction
                            # We append the existing suffix to keep it unique-ish or just random
                            element['action_id'] = f"disabled_{element['action_id']}"
                            
                            if 'text' in element:
                                 element['text']['emoji'] = True

                            # Style the buttons based on correctness
                            if element['value'] == correct_user_id:
                                element['style'] = 'primary'  # Correct answer in green
                            elif element['value'] == selected_user_id:
                                element['style'] = 'danger'   # User's incorrect selection in red
                            else:
                                element.pop('style', None)    # Remove 'style' if any

        if not answer_blocks_found:
            print("No answer action blocks found to update.")
            return

        # Add feedback text at the top
        first_block_text = original_blocks[0]['text']['text']
        is_hard_mode = "Hard Mode" in first_block_text

        if is_correct:
            streak_msg = f" 🔥 {new_streak} Day Streak! (+{streak_points} pts)" if new_streak > 1 else ""
            feedback_text = f"🎉 *Correct!* You really know your colleagues! 🌟\n*+{total_points} Points!*{streak_msg}"
        else:
            correct_name = get_user_name(correct_user_id)
            if is_hard_mode:
                selected_name = get_user_name(selected_user_id)
                feedback_text = f"❌ *Nope!* You selected *{selected_name}*. We were looking for *{correct_name}*! 🍀\n*+{total_points} Points for participating!*"
            else:
                feedback_text = f"❌ *Nope!* This is your amazing colleague *{correct_name}*. Better luck next time! 🍀\n*+{total_points} Points for participating!*"

        # Insert feedback and Next Quiz button at the BOTTOM
        original_blocks.append({"type": "divider"})
        
        original_blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": feedback_text
            }
        })
        
        original_blocks.append({
            "type": "actions",
            "block_id": "next_quiz_block",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Next Quiz"},
                    "value": "next_quiz",
                    "action_id": "next_quiz",
                    "style": "primary"
                }
            ]
        })

        # Extract channel ID and message timestamp from payload
        channel_id = payload['channel']['id']
        message_ts = payload['message']['ts']
        if channel_id.startswith('D'):
            # DM to a specific user (user ID can also start with 'D' sometimes)
            print(f"DM detected, sending response to user ID: {channel_id}")
        else:
            # General channel or private channel
            print(f"Sending response to channel ID: {channel_id}")
        # Update the original message with feedback and disabled buttons
        try:
            print(f"Updating quiz response for user_id: {user_id}, team_id: {team_id}, channel_id: {channel_id}, message_ts: {message_ts}")
            client.chat_update(
                channel=channel_id,
                ts=message_ts,
                blocks=original_blocks,
                text=feedback_text
            )
        except SlackApiError as e:
            print(f"[ERROR] Slack API Error while updating message for user {user_id}: {e.response['error']}")
        except Exception as e:
            print(f"[ERROR] Unexpected error while updating message: {str(e)}")

    finally:
        # Remove the stored answer (delete the quiz session)
        delete_quiz_session(user_id)

def process_random_quizzes():
    """Check for users due for a random quiz and send it."""
    from datetime import datetime, timedelta
    from database_helpers import get_users_due_for_quiz, update_user_quiz_schedule

    now = datetime.utcnow()
    # Simple check for office hours (08:00 - 18:00 UTC for now)
    # TODO: Support user timezones
    if not (8 <= now.hour < 18):
        logger.info("Outside office hours, skipping random quizzes.")
        return

    users = get_users_due_for_quiz()
    logger.info(f"Found {len(users)} users due for a random quiz.")

    for user in users:
        logger.info(f"Sending random quiz to user {user.id} (Team: {user.team_id})")
        success, msg = send_quiz_to_user(user.id, user.team_id)
        
        # Schedule next quiz regardless of success (to avoid retry loops on error)
        # Random interval between 30 mins and 4 hours
        minutes = random.randint(30, 240)
        next_quiz_at = now + timedelta(minutes=minutes)
        
        update_user_quiz_schedule(user.id, next_quiz_at)
        logger.info(f"Scheduled next quiz for user {user.id} at {next_quiz_at} (in {minutes} mins)")