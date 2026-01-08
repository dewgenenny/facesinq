import logging
from slack_sdk.errors import SlackApiError
from database_helpers import (
    get_user_score, 
    get_user_attempts, 
    has_user_opted_in, 
    get_user,
    get_global_stats,
    get_top_scores
)

logger = logging.getLogger(__name__)

def get_home_view(user_id, team_id):
    """Generates the Block Kit payload for the App Home view."""
    
    # Fetch user data
    user = get_user(user_id)
    score, total_attempts = get_user_score(user_id)
    is_opted_in = has_user_opted_in(user_id)
    
    # Determine current difficulty
    difficulty = 'easy'
    if user and hasattr(user, 'difficulty_mode'):
        difficulty = user.difficulty_mode

    # Calculate accuracy
    accuracy = (score / total_attempts * 100) if total_attempts > 0 else 0
    
    # Get Global Stats
    global_stats = get_global_stats()
    
    # Get Leaderboard (Top 3 for Home View)
    top_scores = get_top_scores(limit=3)

    blocks = [
        # Hero Section
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Welcome to FaceSinq! 👋",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Master your team's faces and names. Challenge yourself and climb the leaderboard!"
            }
        },
        {
            "type": "divider"
        },
        
        # Main Actions
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Ready to play?*"
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "▶️ Start Quiz",
                        "emoji": True
                    },
                    "style": "primary",
                    "action_id": "start_quiz_home"
                }
            ]
        },
        {
            "type": "divider"
        },
        
        # User Stats Section
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Your Stats 📊",
                "emoji": True
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Score:*\n{score} / {total_attempts}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Accuracy:*\n{accuracy:.1f}%"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Streak:*\n{user.current_streak if user else 0} 🔥"
                }
            ]
        },
        {
            "type": "divider"
        },
        
        # Leaderboard Preview
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Leaderboard 🏆",
                "emoji": True
            }
        }
    ]
    
    if top_scores:
        for i, (name, pct, img, scr, att, streak) in enumerate(top_scores):
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉"
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "image",
                        "image_url": img,
                        "alt_text": name
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*{medal} {name}*  •  {pct:.0f}% ({scr}/{att})"
                    }
                ]
            })
    else:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "_No scores yet. Be the first!_"
                }
            ]
        })

    blocks.append({"type": "divider"})

    # Settings Section
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": "Settings ⚙️",
            "emoji": True
        }
    })
    
    # Opt-in Toggle
    opt_in_text = "On" if is_opted_in else "Off"
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*Daily Random Quiz*\nReceive a random quiz during office hours."
        },
        "accessory": {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": f"Turn { 'Off' if is_opted_in else 'On' }",
                "emoji": True
            },
            "style": "danger" if is_opted_in else "primary",
            "value": "false" if is_opted_in else "true",
            "action_id": "toggle_opt_in_home"
        }
    })

    # Difficulty Toggle
    is_hard = (difficulty == 'hard')
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"*Difficulty Mode: {difficulty.title()}*\n{'Name -> Photo' if is_hard else 'Photo -> Name'}"
        },
        "accessory": {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": "Switch to Easy" if is_hard else "Switch to Hard",
                "emoji": True
            },
            "value": "easy" if is_hard else "hard",
            "action_id": "toggle_difficulty_home"
        }
    })
    
    return {
        "type": "home",
        "blocks": blocks
    }


def publish_home_view(user_id, team_id, client):
    """Publishes the App Home view for a user."""
    try:
        view = get_home_view(user_id, team_id)
        client.views_publish(
            user_id=user_id,
            view=view
        )
        logger.info(f"Published App Home for user {user_id}")
    except SlackApiError as e:
        logger.error(f"Error publishing App Home: {e.response['error']}")
    except Exception as e:
        logger.error(f"Error generating App Home view: {str(e)}")
