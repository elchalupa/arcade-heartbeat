"""
Decision engine for arcade-heartbeat.

This is the "brain" of the application. It processes chat events, tracks state,
and decides when to trigger notifications based on configurable rules.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from colorama import Fore, Style

from heartbeat.database import ViewerDatabase, Viewer
from heartbeat.prompts import PromptLibrary
from heartbeat.notifier import Notifier


class DecisionEngine:
    """
    The decision engine monitors chat activity and triggers notifications.
    
    It tracks:
    - When the last chat message was received (from anyone)
    - When the streamer last spoke (future: via Speaker.bot integration)
    - Which viewers have been welcomed this session (to prevent spam)
    
    Notification triggers:
    - Chat has been quiet for X minutes
    - A regular viewer returns after being away for Y days
    """
    
    def __init__(
        self,
        config: dict,
        database: ViewerDatabase,
        prompts: PromptLibrary,
        notifier: Notifier
    ):
        """
        Initialize the decision engine.
        
        Args:
            config: Configuration dictionary
            database: Viewer database instance
            prompts: Prompt library instance
            notifier: Notification system instance
        """
        self.config = config
        self.database = database
        self.prompts = prompts
        self.notifier = notifier
        
        # Load thresholds from config
        thresholds = config.get("thresholds", {})
        self.chat_quiet_minutes = thresholds.get("chat_quiet_minutes", 5)
        self.regular_viewer_streams = thresholds.get("regular_viewer_streams", 3)
        self.regular_away_days = thresholds.get("regular_away_days", 2)
        
        # Load cooldowns from config
        cooldowns = config.get("cooldowns", {})
        self.chat_quiet_cooldown = cooldowns.get("chat_quiet_cooldown", 10)
        self.viewer_welcome_cooldown = cooldowns.get("viewer_welcome_cooldown", 0)
        
        # State tracking
        self.last_chat_message_time: datetime = datetime.now()
        self.last_chat_quiet_notification: Optional[datetime] = None
        self.welcomed_viewers: dict[str, datetime] = {}  # username -> last welcomed time
        
        # Debug mode
        self.debug = config.get("logging", {}).get("debug", False)
        
        # Monitoring task handle
        self._monitoring_task: Optional[asyncio.Task] = None
    
    async def start_monitoring(self):
        """
        Start the background monitoring loop.
        
        This runs continuously and checks for conditions that require
        notifications (like chat being quiet for too long).
        """
        if self.debug:
            print(f"{Fore.BLUE}[Debug] Starting monitoring loop{Style.RESET_ALL}")
        
        while True:
            await self._check_chat_quiet()
            # Check every 30 seconds
            await asyncio.sleep(30)
    
    async def _check_chat_quiet(self):
        """
        Check if chat has been quiet for too long.
        
        If chat hasn't seen a message in chat_quiet_minutes, and we haven't
        already notified recently (respecting cooldown), trigger a notification.
        """
        now = datetime.now()
        minutes_since_message = (now - self.last_chat_message_time).total_seconds() / 60
        
        if self.debug:
            print(f"{Fore.BLUE}[Debug] Minutes since last message: {minutes_since_message:.1f}{Style.RESET_ALL}")
        
        # Check if chat has been quiet long enough
        if minutes_since_message < self.chat_quiet_minutes:
            return
        
        # Check cooldown - don't spam notifications
        if self.last_chat_quiet_notification is not None:
            minutes_since_notification = (now - self.last_chat_quiet_notification).total_seconds() / 60
            if minutes_since_notification < self.chat_quiet_cooldown:
                if self.debug:
                    print(f"{Fore.BLUE}[Debug] Chat quiet notification on cooldown ({minutes_since_notification:.1f} min){Style.RESET_ALL}")
                return
        
        # Trigger notification
        print(f"{Fore.MAGENTA}[Heartbeat]{Style.RESET_ALL} → Chat quiet for {int(minutes_since_message)} minutes")
        
        # Get a random prompt for this situation
        prompt = self.prompts.get_chat_quiet_prompt()
        
        # Send notification
        self.notifier.notify_chat_quiet(
            minutes=int(minutes_since_message),
            prompt=prompt
        )
        
        # Update last notification time
        self.last_chat_quiet_notification = now
    
    async def on_message(self, username: str, content: str, is_streamer: bool = False):
        """
        Process an incoming chat message.
        
        This is called by the chat bot for every message received.
        
        Args:
            username: The username of the chatter
            content: The message content
            is_streamer: Whether this message is from the channel owner
        """
        now = datetime.now()
        
        # Update last message time (resets the quiet timer)
        self.last_chat_message_time = now
        
        # Don't track the streamer as a viewer
        if is_streamer:
            if self.debug:
                print(f"{Fore.BLUE}[Debug] Streamer message, not tracking{Style.RESET_ALL}")
            return
        
        # Record this message in the database
        viewer, is_new, is_returning = self.database.record_message(username)
        
        # Handle new viewer
        if is_new:
            print(f"{Fore.CYAN}[Heartbeat]{Style.RESET_ALL} → New viewer: {Fore.GREEN}{username}{Style.RESET_ALL}")
            # We could notify here, but for v1 we only notify for returning regulars
        
        # Handle returning regular viewer
        elif is_returning:
            # Check cooldown for this specific viewer
            if username.lower() in self.welcomed_viewers:
                last_welcomed = self.welcomed_viewers[username.lower()]
                minutes_since = (now - last_welcomed).total_seconds() / 60
                if self.viewer_welcome_cooldown > 0 and minutes_since < self.viewer_welcome_cooldown:
                    if self.debug:
                        print(f"{Fore.BLUE}[Debug] Viewer {username} welcome on cooldown{Style.RESET_ALL}")
                    return
            
            # Calculate days away (stored by database during record_message)
            days_away = getattr(viewer, '_days_away', viewer.days_since_last_seen)
            
            # Only notify if they've been away long enough
            if days_away >= self.regular_away_days:
                print(f"{Fore.MAGENTA}[Heartbeat]{Style.RESET_ALL} → Regular returning: {Fore.GREEN}{username}{Style.RESET_ALL} (last seen {days_away} days ago)")
                
                # Get a prompt for this situation
                prompt = self.prompts.get_viewer_return_prompt(
                    username=username,
                    days_ago=days_away,
                    stream_count=viewer.stream_count
                )
                
                # Send notification
                self.notifier.notify_viewer_return(
                    username=username,
                    days_ago=days_away,
                    stream_count=viewer.stream_count,
                    prompt=prompt
                )
                
                # Mark as welcomed
                self.welcomed_viewers[username.lower()] = now
