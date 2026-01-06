"""
Database Connection Utility
Handles Supabase database connections for data ingestion
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file in project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)  # This will also load from current directory if project root doesn't have it
load_dotenv()  # Also try loading from current directory


def get_db_connection_string() -> str:
    """
    Get database connection string from environment variable.
    
    Checks DATABASE_URL first, then SUPABASE_DB_URL as fallback.
    
    Returns:
        Database connection string
    
    Raises:
        ValueError: If no valid database URL is found
    """
    database_url = os.getenv('DATABASE_URL') or os.getenv('SUPABASE_DB_URL')
    
    if not database_url:
        raise ValueError(
            "DATABASE_URL or SUPABASE_DB_URL environment variable must be set"
        )
    
    if not database_url.startswith('postgresql://') and not database_url.startswith('postgres://'):
        raise ValueError("Invalid DATABASE_URL format. Must start with postgresql:// or postgres://")
    
    return database_url


def create_db_engine() -> Engine:
    """
    Create SQLAlchemy database engine.
    
    Returns:
        SQLAlchemy Engine instance
    """
    connection_string = get_db_connection_string()
    engine = create_engine(
        connection_string,
        pool_pre_ping=True,  # Verify connections before using
        echo=False,  # Set to True for SQL debugging
    )
    return engine


def get_db_connection():
    """
    Get database connection (for pandas/sqlalchemy use).
    
    Returns:
        Database connection object
    """
    engine = create_db_engine()
    return engine.connect()


def test_connection() -> bool:
    """
    Test database connection.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        connection_string = get_db_connection_string()
        print("Testing database connection...")
        
        engine = create_db_engine()
        with engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
            conn.commit()
        print("Database connection successful!")
        return True
    except ValueError as e:
        print(f"Configuration error: {e}")
        return False
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False


if __name__ == "__main__":
    test_connection()

