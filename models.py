from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from db import Base
from cryptography.fernet import Fernet
import os

# Load encryption key from environment variable
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')

fernet = Fernet(ENCRYPTION_KEY)

class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True)
    team_id = Column(String, nullable=False)  # Track which Slack team this user belongs to
    name_encrypted = Column(String, nullable=False)
    image_encrypted = Column(String)
    opted_in = Column(Boolean, default=False)

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
    user = relationship('User', back_populates='scores')

    def __repr__(self):
        return f"<Score {self.user_id}: {self.score}>"

class QuizSession(Base):
    __tablename__ = 'quiz_sessions'

    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    correct_user_id = Column(String, nullable=False)

    user = relationship("User", back_populates="quiz_sessions")

# # Define relationships after all classes are defined
# User.scores = db.relationship('Score', back_populates='user')
# User.quiz_sessions = db.relationship("QuizSession", back_populates="user")

class Workspace(Base):
    __tablename__ = 'workspaces'
    id = Column(String, primary_key=True)  # This will store the team_id
    name = Column(String)  # Optionally, store the workspace name for reference

    def __repr__(self):
        return f"<Workspace {self.name} ({self.id})>"

def encrypt_value(value):
    return fernet.encrypt(value.encode()).decode() if value else None

def decrypt_value(value):
    return fernet.decrypt(value.encode()).decode() if value else None