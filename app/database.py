import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sessions.db")

def init_db():
    """Initializes the SQLite database and creates the sessions table if it doesn't exist."""
    # Ensure data directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            messages TEXT,
            parameters TEXT,
            final_itinerary TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def get_session(session_id: str) -> dict | None:
    """Retrieves a session from the database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "session_id": row["session_id"],
            "messages": json.loads(row["messages"]) if row["messages"] else [],
            "parameters": json.loads(row["parameters"]) if row["parameters"] else {},
            "final_itinerary": row["final_itinerary"]
        }
    return None

def save_session(session_id: str, messages: list, parameters: dict = None, final_itinerary: str = None):
    """Saves or updates a session in the database."""
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if session exists
    cursor.execute("SELECT session_id FROM sessions WHERE session_id = ?", (session_id,))
    exists = cursor.fetchone()
    
    messages_json = json.dumps(messages)
    parameters_json = json.dumps(parameters) if parameters else "{}"
    
    if exists:
        cursor.execute('''
            UPDATE sessions 
            SET messages = ?, parameters = ?, final_itinerary = ?, updated_at = ?
            WHERE session_id = ?
        ''', (messages_json, parameters_json, final_itinerary, now, session_id))
    else:
        cursor.execute('''
            INSERT INTO sessions (session_id, messages, parameters, final_itinerary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session_id, messages_json, parameters_json, final_itinerary, now, now))
        
    conn.commit()
    conn.close()

# Initialize the database on import
init_db()
