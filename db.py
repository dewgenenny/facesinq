import sqlite3

def init_db():
    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    # Create tables for users and scores
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            user_id TEXT PRIMARY KEY,
            score INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()
