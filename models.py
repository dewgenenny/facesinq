from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from db import Base

class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    image = Column(String)
    opted_in = Column(Boolean, default=False)

    scores = relationship('Score', back_populates='user')
    quiz_sessions = relationship("QuizSession", back_populates="user")

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