import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from models import User, Score, QuizSession
from db import Session
from database_helpers import update_user_streak, update_score, get_user, get_top_scores
from game_manager import handle_quiz_response
from leaderboard import get_leaderboard_blocks

class TestScoring(unittest.TestCase):
    def setUp(self):
        # Create a test user
        self.user_id = "TEST_USER_SCORING"
        self.team_id = "TEST_TEAM_SCORING"
        self.correct_user_id = "TEST_COLLEAGUE"
        
        with Session() as session:
            # Clean up
            session.query(User).filter_by(id=self.user_id).delete()
            session.query(Score).filter_by(user_id=self.user_id).delete()
            session.query(QuizSession).filter_by(user_id=self.user_id).delete()
            
            # Create user
            user = User(id=self.user_id, team_id=self.team_id, name_encrypted="Test", opted_in=True)
            session.add(user)
            
            # Create active quiz session
            quiz = QuizSession(user_id=self.user_id, correct_user_id=self.correct_user_id)
            session.add(quiz)
            
            # Create Colleagues (dummy)
            colleague = User(id=self.correct_user_id, team_id=self.team_id, name_encrypted="Colleague")
            session.merge(colleague)
            
            session.commit()

    def tearDown(self):
        with Session() as session:
            session.query(User).filter_by(id=self.user_id).delete()
            session.query(Score).filter_by(user_id=self.user_id).delete()
            session.query(User).filter_by(id=self.correct_user_id).delete()
            session.commit()

    @patch('game_manager.get_slack_client')
    @patch('game_manager.delete_quiz_session') # Don't actually delete so we can reuse setup if needed, or mock it
    def test_scoring_flow(self, mock_delete, mock_get_client):
        # Mock Slack client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # 1. Correct Answer - First time
        print("\nTesting: Correct Answer (First Time)")
        payload = {
            'message': {'blocks': [], 'ts': '123'},
            'actions': [{'action_id': 'ans_0'}],
            'channel': {'id': 'C123'}
        }
        
        handle_quiz_response(self.user_id, self.correct_user_id, payload, self.team_id)
        
        # Verify DB
        with Session() as session:
            user = session.query(User).filter_by(id=self.user_id).one()
            score = session.query(Score).filter_by(user_id=self.user_id).one()
            
            print(f"User Streak: {user.current_streak}")
            print(f"Score: {score.score}")
            
            self.assertEqual(user.current_streak, 1)
            self.assertEqual(score.score, 10) # 10 base + 0 bonus? or 10 base + 1*5? Code: min(streak, 10) * 5. Streak is 1. so 5. 10+5=15.
            # Wait, let's check my logic in Step 63:
            # streak_bonus_multiplier = min(new_streak, 10) -> min(1, 10) = 1
            # streak_points = 1 * 5 = 5
            # total_points = 10 + 5 = 15.
            self.assertEqual(score.score, 15)
            self.assertIsNotNone(user.last_answered_at)

        # 2. Simulate "Tomorrow"
        print("\nTesting: Correct Answer (Next Day Streak)")
        with Session() as session:
            user = session.query(User).filter_by(id=self.user_id).one()
            # Move last_answered_at to yesterday
            user.last_answered_at = datetime.utcnow() - timedelta(days=1)
            # Ensure quiz session exists again (handle_quiz_response deletes it)
            quiz = QuizSession(user_id=self.user_id, correct_user_id=self.correct_user_id)
            session.merge(quiz)
            session.commit()
            
        handle_quiz_response(self.user_id, self.correct_user_id, payload, self.team_id)
        
        with Session() as session:
            user = session.query(User).filter_by(id=self.user_id).one()
            score = session.query(Score).filter_by(user_id=self.user_id).one()
            
            print(f"User Streak: {user.current_streak}")
            print(f"Total Score: {score.score}")
            
            self.assertEqual(user.current_streak, 2)
            # Points: Previous 15. New: 10 base + (2*5 streak) = 20. Total 35.
            self.assertEqual(score.score, 35)

        # 3. Incorrect Answer (Participation)
        print("\nTesting: Incorrect Answer")
        with Session() as session:
            # Ensure quiz session exists
            quiz = QuizSession(user_id=self.user_id, correct_user_id=self.correct_user_id)
            session.merge(quiz)
            session.commit()

        handle_quiz_response(self.user_id, "WRONG_ID", payload, self.team_id)
        
        with Session() as session:
            user = session.query(User).filter_by(id=self.user_id).one()
            score = session.query(Score).filter_by(user_id=self.user_id).one()
            
            print(f"User Streak (after wrong): {user.current_streak}")
            print(f"Total Score: {score.score}")
            
            # Streak should stay same (2) or increment?
            # Code:
            # if last_date == today_date: pass (already answered today)
            # We are running immediately, so last_answered is NOW (from step 2).
            # So streak stays 2.
            self.assertEqual(user.current_streak, 2)
            
            # Points: Previous 35. New: 2 base. Total 37.
            self.assertEqual(score.score, 37)

    def test_leaderboard(self):
        print("\nTesting: Leaderboard Generation")
        with Session() as session:
             # Create a user with high score and streak
             user = User(id="LDR_USER", team_id="TEAM", name_encrypted="LeaderUser", opted_in=True, current_streak=5)
             score = Score(user_id="LDR_USER", score=1000, total_attempts=50) # > 10 attempts
             session.merge(user)
             session.merge(score)
             session.commit()
             
        blocks = get_leaderboard_blocks()
        print("Generated Blocks:")
        for block in blocks:
             if block['type'] == 'section' and 'text' in block and 'LeaderUser' in block['text']['text']:
                 print(block['text']['text'])
                 self.assertIn("🔥 5", block['text']['text'])
                 self.assertIn("1000 pts", block['text']['text'])

        # Clean up
        with Session() as session:
             session.query(User).filter_by(id="LDR_USER").delete()
             session.query(Score).filter_by(user_id="LDR_USER").delete()
             session.commit()

if __name__ == "__main__":
    unittest.main()
