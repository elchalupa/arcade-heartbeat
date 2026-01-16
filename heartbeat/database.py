"""
Viewer database for arcade-heartbeat.

Stores viewer history in SQLite, persisted in %APPDATA%/arcade-heartbeat/.
Tracks when viewers were first/last seen, message counts, and stream attendance.
"""

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class Viewer:
    """Represents a viewer from the database."""
    username: str
    first_seen: datetime
    last_seen: datetime
    message_count: int
    stream_count: int
    current_stream_id: Optional[str] = None
    
    @property
    def days_since_last_seen(self) -> int:
        """Calculate days since viewer was last seen."""
        delta = datetime.now() - self.last_seen
        return delta.days
    
    def is_regular(self, threshold: int = 3) -> bool:
        """Check if viewer qualifies as a 'regular' based on stream attendance."""
        return self.stream_count >= threshold


class ViewerDatabase:
    """
    SQLite database for tracking viewer history.
    
    The database is stored in %APPDATA%/arcade-heartbeat/viewers.db on Windows.
    This ensures data persists across reinstalls and updates.
    """
    
    def __init__(self, db_path: Path = None):
        """
        Initialize the database connection.
        
        Args:
            db_path: Custom path for database file. If None, uses %APPDATA%.
        """
        if db_path is None:
            # Use %APPDATA% on Windows for persistent storage
            appdata = os.getenv("APPDATA")
            if appdata:
                db_dir = Path(appdata) / "arcade-heartbeat"
            else:
                # Fallback for non-Windows systems
                db_dir = Path.home() / ".arcade-heartbeat"
            
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = db_dir / "viewers.db"
        
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        
        # Generate a unique ID for this stream session
        self.stream_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create tables if they don't exist
        self._init_tables()
    
    def _init_tables(self):
        """Create database tables if they don't exist."""
        cursor = self.conn.cursor()
        
        # Main viewers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS viewers (
                username TEXT PRIMARY KEY,
                first_seen TIMESTAMP NOT NULL,
                last_seen TIMESTAMP NOT NULL,
                message_count INTEGER DEFAULT 0,
                stream_count INTEGER DEFAULT 1,
                current_stream_id TEXT
            )
        """)
        
        # Index for faster lookups on last_seen (for "returning" queries)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_last_seen ON viewers(last_seen)
        """)
        
        self.conn.commit()
    
    def get_viewer(self, username: str) -> Optional[Viewer]:
        """
        Get a viewer by username.
        
        Args:
            username: Twitch username (case-insensitive, stored lowercase)
            
        Returns:
            Viewer object if found, None otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM viewers WHERE username = ?",
            (username.lower(),)
        )
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        return Viewer(
            username=row["username"],
            first_seen=datetime.fromisoformat(row["first_seen"]),
            last_seen=datetime.fromisoformat(row["last_seen"]),
            message_count=row["message_count"],
            stream_count=row["stream_count"],
            current_stream_id=row["current_stream_id"]
        )
    
    def record_message(self, username: str) -> tuple[Viewer, bool, bool]:
        """
        Record a chat message from a viewer.
        
        This is the main method called when someone chats. It handles:
        - Creating new viewer records
        - Updating last_seen and message_count
        - Incrementing stream_count if this is a new stream session
        
        Args:
            username: Twitch username of the chatter
            
        Returns:
            Tuple of (Viewer object, is_new_viewer, is_returning_regular)
            - is_new_viewer: True if this is their first ever message
            - is_returning_regular: True if they're a regular who hasn't been 
              seen in a while (check viewer.days_since_last_seen for details)
        """
        username = username.lower()
        now = datetime.now()
        
        # Check if viewer exists
        existing = self.get_viewer(username)
        
        if existing is None:
            # Brand new viewer - create record
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO viewers (username, first_seen, last_seen, message_count, stream_count, current_stream_id)
                VALUES (?, ?, ?, 1, 1, ?)
            """, (username, now.isoformat(), now.isoformat(), self.stream_id))
            self.conn.commit()
            
            new_viewer = self.get_viewer(username)
            return (new_viewer, True, False)
        
        # Existing viewer - check if this is a new stream session for them
        is_new_stream = existing.current_stream_id != self.stream_id
        
        # Capture their previous last_seen before we update it
        previous_last_seen = existing.last_seen
        days_away = (now - previous_last_seen).days
        
        # Update the record
        cursor = self.conn.cursor()
        if is_new_stream:
            # New stream session - increment stream_count
            cursor.execute("""
                UPDATE viewers 
                SET last_seen = ?, 
                    message_count = message_count + 1,
                    stream_count = stream_count + 1,
                    current_stream_id = ?
                WHERE username = ?
            """, (now.isoformat(), self.stream_id, username))
        else:
            # Same stream session - just update message count and last_seen
            cursor.execute("""
                UPDATE viewers 
                SET last_seen = ?, 
                    message_count = message_count + 1
                WHERE username = ?
            """, (now.isoformat(), username))
        
        self.conn.commit()
        
        # Get updated viewer record
        updated_viewer = self.get_viewer(username)
        
        # Determine if this is a "returning regular"
        # They must have been away for a while AND be a regular
        is_returning = is_new_stream and days_away >= 2 and existing.is_regular()
        
        # Temporarily set days_since_last_seen to the pre-update value for the notification
        if is_returning:
            updated_viewer._days_away = days_away
        
        return (updated_viewer, False, is_returning)
    
    def get_viewer_count(self) -> int:
        """Get total number of unique viewers in database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM viewers")
        return cursor.fetchone()[0]
    
    def get_regulars(self, min_streams: int = 3) -> list[Viewer]:
        """
        Get all viewers who qualify as regulars.
        
        Args:
            min_streams: Minimum stream count to be considered regular
            
        Returns:
            List of Viewer objects
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM viewers WHERE stream_count >= ? ORDER BY stream_count DESC",
            (min_streams,)
        )
        
        return [
            Viewer(
                username=row["username"],
                first_seen=datetime.fromisoformat(row["first_seen"]),
                last_seen=datetime.fromisoformat(row["last_seen"]),
                message_count=row["message_count"],
                stream_count=row["stream_count"],
                current_stream_id=row["current_stream_id"]
            )
            for row in cursor.fetchall()
        ]
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
