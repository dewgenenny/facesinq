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
    score, total_attempts, correct_attempts = get_user_score(user_id)
    is_opted_in = has_user_opted_in(user_id)
    
    # Determine current difficulty
    difficulty = 'easy'
    if user and hasattr(user, 'difficulty_mode'):
        difficulty = user.difficulty_mode

    # Calculate accuracy
    accuracy = (correct_attempts / total_attempts * 100) if total_attempts > 0 else 0
    
    # Get Global Stats
    global_stats = get_global_stats()
    
    # Get Leaderboard (Top 3 for Home View)
    top_scores = get_top_scores(limit=3)

    # Hero Section
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "FaceSinq",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Learn names faster with quick quizzes. Track accuracy and streaks."
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
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "🏆 Leaderboard",
                        "emoji": True
                    },
                    "action_id": "view_leaderboard_home" # We might need a handler for this, or just let it link to something? 
                    # Existing plan didn't specify a handler, let's keep it consistent or simple. 
                    # Actually, we can just trigger the leaderboard modal or message. 
                    # For now, let's assume it triggers the same leaderboard logic.
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "❓ Help",
                        "emoji": True
                    },
                    "url": "https://github.com/dewgenenny/facesinq", # Placeholder link
                    "action_id": "help_home"
                }
            ]
        },
        {"type": "divider"}
    ]

    # Stats or Onboarding Section
    if total_attempts == 0:
        # Onboarding State
        blocks.extend([
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Welcome!* 👋\nTake your first quiz to start tracking your stats and climbing the leaderboard."
                },
                "accessory": {
                   "type": "button",
                   "text": {"type": "plain_text", "text": "Start First Quiz"},
                   "style": "primary",
                   "action_id": "start_quiz_home"
                }
            }
        ])
    else:
        # Stats State
        streak_text = f"{user.current_streak} 🔥" if user and user.current_streak > 0 else f"{user.current_streak}"
        diff_display = difficulty.title()
        opt_in_display = "Enabled" if is_opted_in else "Disabled"
        
        blocks.extend([
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Your Stats*"}
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"Score: *{score}/{total_attempts}*"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"Accuracy: *{accuracy:.0f}%*"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"Streak: *{streak_text}*"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"⚙️ Difficulty: *{diff_display}*  •  📅 Daily Quiz: *{opt_in_display}*"
                    }
                ]
            }
        ])

    blocks.append({"type": "divider"})

    # Leaderboard Section (Compact)
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*Top Players* 🏆"
        },
        "accessory": {
            "type": "button",
             "text": {"type": "plain_text", "text": "View Full"},
             "action_id": "view_leaderboard_home"
        }
    })

    if top_scores:
        leaderboard_text = ""
        for i, (name, pct, img, scr, att, streak) in enumerate(top_scores):
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉"
            leaderboard_text += f"{medal} *{name}* — {pct:.0f}% ({scr}/{att})\n"
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": leaderboard_text
            }
        })
    else:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "_No scores yet._"}]
        })

    blocks.append({"type": "divider"})

    # Settings Section (Using Selects)
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": "*Settings*"}
    })

    # Opt-in Select
    opt_in_option = {
        "text": {"type": "plain_text", "text": "Enabled"},
        "value": "true"
    } if is_opted_in else {
        "text": {"type": "plain_text", "text": "Disabled"},
        "value": "false"
    }

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "📅 *Daily Random Quiz*"
        },
        "accessory": {
            "type": "static_select",
            "placeholder": {"type": "plain_text", "text": "Select status"},
            "initial_option": opt_in_option,
            "options": [
                {
                    "text": {"type": "plain_text", "text": "Enabled"},
                    "value": "true"
                },
                {
                    "text": {"type": "plain_text", "text": "Disabled"},
                    "value": "false"
                }
            ],
            "action_id": "toggle_opt_in_home"
        }
    })

    # Difficulty Select
    diff_option = {
        "text": {"type": "plain_text", "text": "Easy (Photo → Name)"},
        "value": "easy"
    } if difficulty == 'easy' else {
        "text": {"type": "plain_text", "text": "Hard (Name → Photo)"},
        "value": "hard"
    }

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "🧠 *Difficulty Mode*"
        },
        "accessory": {
            "type": "static_select",
            "placeholder": {"type": "plain_text", "text": "Select difficulty"},
            "initial_option": diff_option,
            "options": [
                {
                    "text": {"type": "plain_text", "text": "Easy (Photo → Name)"},
                    "value": "easy"
                },
                {
                    "text": {"type": "plain_text", "text": "Hard (Name → Photo)"},
                    "value": "hard"
                }
            ],
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
