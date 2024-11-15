# db.py
import sqlite3

def init_db():
    conn = sqlite3.connect('facesinq.db')
    c = conn.cursor()
    # Create tables for users and scores
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT,
            image TEXT,
            opted_in INTEGER DEFAULT 0
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

def migrate_db():
    conn = sqlite3.connect('facesinq.db')
    c = conn.cursor()
    c.execute("PRAGMA table_info(quiz_sessions)")
    columns = [column[1] for column in c.fetchall()]
    if not columns:
        # Create the quiz_sessions table
        c.execute('''
            CREATE TABLE IF NOT EXISTS quiz_sessions (
                user_id TEXT PRIMARY KEY,
                correct_user_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
    conn.close()

