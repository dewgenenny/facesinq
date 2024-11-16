# models.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String, nullable=False)
    image = db.Column(db.String)
    opted_in = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<User {self.name}>"

class Score(db.Model):
    __tablename__ = 'scores'
    user_id = db.Column(db.String, db.ForeignKey('users.id'), primary_key=True)
    score = db.Column(db.Integer, default=0)
    user = db.relationship('User', back_populates='scores')

    def __repr__(self):
        return f"<Score {self.user_id}: {self.score}>"

User.scores = db.relationship('Score', back_populates='user')
