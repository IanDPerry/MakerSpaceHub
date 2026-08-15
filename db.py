import os
import mysql.connector
from dotenv import load_dotenv

# refactor example.env to local.env and your credentials will be loaded from local.env
load_dotenv("local.env")

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password=os.environ.get("DB_PASSWORD"),
        database="makerspacehub"
    )

def log_action(cursor, user_id, action):
    """FR-17: append-only audit trail, shared across all service modules."""
    cursor.execute(
        "INSERT INTO AuditLogs (userID, action) VALUES (%s, %s)",
        (user_id, action)
    )