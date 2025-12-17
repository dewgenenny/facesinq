# models.py
import logging
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from db import Base
from cryptography.fernet import Fernet
import os
import binascii

logger = logging.getLogger(__name__)

# Load encryption key from environment variable
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')

if ENCRYPTION_KEY:
    ENCRYPTION_KEY = ENCRYPTION_KEY.strip()  # Remove potential surrounding whitespace/newlines

try:
    if not ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY environment variable is missing.")
    
    fernet = Fernet(ENCRYPTION_KEY)
    logger.info("Encryption key loaded and verified successfully.")

except (ValueError, binascii.Error) as e:
    logger.critical(f"Invalid ENCRYPTION_KEY: {e}. Ensure it is a 32-byte url-safe base64-encoded string. Key length: {len(ENCRYPTION_KEY) if ENCRYPTION_KEY else 0}")
    # We might want to re-raise or handle this gracefully depending on app requirements
    # Re-raising to ensure the app doesn't start with broken encryption
    raise e
except Exception as e:
    logger.critical(f"Unexpected error loading encryption key: {e}")
    raise e

class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True)
    team_id = Column(String, nullable=False)  # Track which Slack team this user belongs to
    name_encrypted = Column(String, nullable=False)
    image_encrypted = Column(String)
    opted_in = Column(Boolean, default=False)
    last_quiz_sent_at = Column(DateTime, nullable=True)
    next_random_quiz_at = Column(DateTime, nullable=True)

    scores = relationship('Score', back_populates='user')
    quiz_sessions = relationship("QuizSession", back_populates="user")

    @property
    def name(self):
        # Decrypt name when accessed
        return decrypt_value(self.name_encrypted)

    @name.setter
    def name(self, value):
        # Encrypt name when setting it
        self.name_encrypted = encrypt_value(value)

    @property
    def image(self):
        # Decrypt image when accessed
        return decrypt_value(self.image_encrypted)

    @image.setter
    def image(self, value):
        # Encrypt image when setting it
        self.image_encrypted = encrypt_value(value)

    def __repr__(self):
        return f"<User {self.name}>"

class Score(Base):
    __tablename__ = 'scores'
    user_id = Column(String, ForeignKey('users.id'), primary_key=True)
    score = Column(Integer, default=0)
    total_attempts = Column(Integer, default=0)
    user = relationship('User', back_populates='scores')

    def __repr__(self):
        return f"<Score {self.user_id}: {self.score}>"

class QuizSession(Base):
    __tablename__ = 'quiz_sessions'

    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    correct_user_id = Column(String, nullable=False)

    user = relationship("User", back_populates="quiz_sessions")

class ScoreHistory(Base):
    __tablename__ = 'score_history'
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    score = Column(Integer, default=0) # 0 or 1 for this attempt
    created_at = Column(DateTime, nullable=False)

    user = relationship("User")

# # Define relationships after all classes are defined
# User.scores = db.relationship('Score', back_populates='user')
# User.quiz_sessions = db.relationship("QuizSession", back_populates="user")

class Workspace(Base):
    __tablename__ = 'workspaces'
    id = Column(String, primary_key=True)  # This is the workspace/team ID
    name = Column(String, nullable=False)
    access_token_encrypted = Column(String, nullable=False)

    def __repr__(self):
        return f"<Workspace id={self.id}, name={self.name}>"

    # Access token property for encryption/decryption
    @property
    def access_token(self):
        # Decrypt access token when accessed
        return fernet.decrypt(self.access_token_encrypted.encode()).decode()

    @access_token.setter
    def access_token(self, value):
        # Encrypt access token when setting it
        self.access_token_encrypted = fernet.encrypt(value.encode()).decode()

def encrypt_value(value):
    return fernet.encrypt(value.encode()).decode() if value else None

def decrypt_value(value):
    return fernet.decrypt(value.encode()).decode() if value else None