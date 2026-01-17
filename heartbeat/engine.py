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
    - A viewer hits a stream attendance milestone
    - Someone raids the channel
    - Someone subscribes, gifts, or resubs
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
        
        # Streak milestone thresholds (stream attendance)
        self.loyalty_milestones = thresholds.get("loyalty_milestones", [5, 10, 25, 50, 100])
        
        # Load cooldowns from config
        cooldowns = config.get("cooldowns", {})
        self.chat_quiet_cooldown = cooldowns.get("chat_quiet_cooldown", 10)
        self.viewer_welcome_cooldown = cooldowns.get("viewer_welcome_cooldown", 0)
        
        # Load notification toggles
        notifications = config.get("notifications", {})
        self.notify_raids = notifications.get("raids", True)
        self.notify_subs = notifications.get("subscriptions", True)
        self.notify_loyalty_milestones = notifications.get("loyalty_milestones", True)
        
        # State tracking
        self.last_chat_message_time: datetime = datetime.now()
        self.last_chat_quiet_notification: Optional[datetime] = None
        self.welcomed_viewers: dict[str, datetime] = {}  # username -> last welcomed time
        self.celebrated_milestones: dict[str, int] = {}  # username -> last celebrated milestone
        
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
        # Capture task reference for graceful shutdown
        self._monitoring_task = asyncio.current_task()
        
        if self.debug:
            print(f"{Fore.BLUE}[Debug] Starting monitoring loop{Style.RESET_ALL}")
        
        try:
            while True:
                await self._check_chat_quiet()
                # Check every 30 seconds
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            # Clean shutdown requested
            if self.debug:
                print(f"{Fore.BLUE}[Debug] Monitoring loop stopped{Style.RESET_ALL}")
            raise
    
    async def stop_monitoring(self):
        """
        Stop the background monitoring loop gracefully.
        
        Cancels the monitoring task and waits for it to finish.
        """
        if self._monitoring_task is None:
            return
        
        if self.debug:
            print(f"{Fore.BLUE}[Debug] Cancelling monitoring task{Style.RESET_ALL}")
        
        self._monitoring_task.cancel()
        try:
            await self._monitoring_task
        except asyncio.CancelledError:
            pass
        
        self._monitoring_task = None
    
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
        
        # Check for streak milestones (for all viewers, not just returning)
        if self.notify_loyalty_milestones:
            await self._check_loyalty_milestone(viewer)
    
    async def _check_loyalty_milestone(self, viewer: Viewer):
        """
        Check if a viewer has hit a stream attendance milestone.
        
        Args:
            viewer: The viewer to check
        """
        username = viewer.username.lower()
        stream_count = viewer.stream_count
        
        # Find the highest milestone they've reached
        reached_milestone = None
        for milestone in sorted(self.loyalty_milestones, reverse=True):
            if stream_count >= milestone:
                reached_milestone = milestone
                break
        
        if reached_milestone is None:
            return
        
        # Check if we've already celebrated this milestone
        last_celebrated = self.celebrated_milestones.get(username, 0)
        if reached_milestone <= last_celebrated:
            return
        
        # Only celebrate if they just hit it (stream_count equals the milestone)
        if stream_count != reached_milestone:
            return
        
        print(f"{Fore.MAGENTA}[Heartbeat]{Style.RESET_ALL} → {Fore.GREEN}{viewer.username}{Style.RESET_ALL} hit {Fore.YELLOW}{stream_count} streams{Style.RESET_ALL}!")
        
        # Send notification
        self.notifier.notify_viewer_milestone(
            username=viewer.username,
            stream_count=stream_count
        )
        
        # Record that we celebrated this milestone
        self.celebrated_milestones[username] = reached_milestone
    
    async def on_raid(self, raider: str, viewer_count: int):
        """
        Process an incoming raid.
        
        Args:
            raider: The username/channel name of the raider
            viewer_count: Number of viewers in the raid
        """
        if not self.notify_raids:
            return
        
        print(f"{Fore.MAGENTA}[Heartbeat]{Style.RESET_ALL} → Raid from {Fore.YELLOW}{raider}{Style.RESET_ALL} with {Fore.GREEN}{viewer_count}{Style.RESET_ALL} viewers!")
        
        # Send notification
        self.notifier.notify_raid(
            raider=raider,
            viewer_count=viewer_count
        )
    
    async def on_subscription(
        self,
        username: Optional[str],
        sub_type: str,
        sub_plan: str,
        months: int,
        gifter: Optional[str],
        gift_count: Optional[int],
        streak: int = 0,
        total_gifts: int = 0
    ):
        """
        Process a subscription event.
        
        Args:
            username: The subscriber's username (None for gift bombs)
            sub_type: Type of sub (sub, resub, gift, gift_bomb, prime_upgrade, gift_upgrade)
            sub_plan: Subscription tier (Prime, Tier 1, Tier 2, Tier 3)
            months: Total months subscribed
            gifter: Username of gifter (for gift subs)
            gift_count: Number of gifts (for gift bombs)
            streak: Current sub streak (for resubs)
            total_gifts: Gifter's total gift count in channel
        """
        if not self.notify_subs:
            return
        
        # Send notification based on sub type
        self.notifier.notify_subscription(
            username=username,
            sub_type=sub_type,
            sub_plan=sub_plan,
            months=months,
            gifter=gifter,
            gift_count=gift_count,
            streak=streak,
            total_gifts=total_gifts
        )
    
    async def on_watch_streak(self, username: str, streak_count: int):
        """
        Process a Twitch watch streak share.
        
        Called when a viewer shares their watch streak in chat.
        
        Args:
            username: The viewer's username
            streak_count: Their current watch streak count
        """
        notify_watch_streaks = self.config.get("notifications", {}).get("watch_streaks", True)
        if not notify_watch_streaks:
            return
        
        print(f"{Fore.MAGENTA}[Heartbeat]{Style.RESET_ALL} → {Fore.GREEN}{username}{Style.RESET_ALL} shared {Fore.YELLOW}{streak_count} stream{Style.RESET_ALL} watch streak!")
        
        # Send notification
        self.notifier.notify_watch_streak(
            username=username,
            streak_count=streak_count
        )
