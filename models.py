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
    name_encrypted = Column(String, nullable=False)
    image_encrypted = Column(String)
    opted_in = Column(Boolean, default=False)

    scores = relationship('Score', back_populates='user')
    quiz_sessions = relationship("QuizSession", back_populates="user")

    @property
    def name(self):
        # Decrypt name when accessed
        return fernet.decrypt(self.name_encrypted.encode()).decode()

    @name.setter
    def name(self, value):
        # Encrypt name when setting it
        self.name_encrypted = fernet.encrypt(value.encode()).decode()

    @property
    def image(self):
        # Decrypt image when accessed
        return fernet.decrypt(self.image_encrypted.encode()).decode() if self.image_encrypted else None

    @image.setter
    def image(self, value):
        # Encrypt image when setting it
        if value:
            self.image_encrypted = fernet.encrypt(value.encode()).decode()
        else:
            self.image_encrypted = None

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
