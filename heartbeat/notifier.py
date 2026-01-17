"""
Cross-platform notification system for arcade-heartbeat.

Detects the operating system and uses the appropriate backend:
- Windows: winotify (native toast notifications)
- macOS/Linux: plyer (cross-platform notifications)
"""

import sys
from typing import Optional

# Detect platform and import appropriate backend
PLATFORM = sys.platform

if PLATFORM == "win32":
    try:
        from winotify import Notification, audio
        BACKEND = "winotify"
    except ImportError:
        BACKEND = None
else:
    try:
        from plyer import notification as plyer_notification
        BACKEND = "plyer"
    except ImportError:
        BACKEND = None


class Notifier:
    """
    Handles sending native notifications across platforms.
    
    All notifications use the same app identity but different titles
    and messages based on the notification type.
    """
    
    def __init__(self, config: dict):
        """
        Initialize the notifier.
        
        Args:
            config: Configuration dictionary
        """
        notif_config = config.get("notifications", {})
        
        self.app_name = notif_config.get("app_name", "Heartbeat")
        self.sound_enabled = notif_config.get("sound", True)
        self.duration = notif_config.get("duration", "long")
        
        # Timeout in seconds for plyer (macOS/Linux)
        # "short" = 5 seconds, "long" = 10 seconds
        self.timeout_seconds = 10 if self.duration == "long" else 5
        
        # Icon path (could be customized later)
        self.icon_path = ""
        
        # Warn if no backend available
        if BACKEND is None:
            from colorama import Fore, Style
            if PLATFORM == "win32":
                print(f"{Fore.YELLOW}[Heartbeat]{Style.RESET_ALL} winotify not installed, notifications disabled")
                print(f"{Fore.YELLOW}[Heartbeat]{Style.RESET_ALL} Install with: pip install winotify")
            else:
                print(f"{Fore.YELLOW}[Heartbeat]{Style.RESET_ALL} plyer not installed, notifications disabled")
                print(f"{Fore.YELLOW}[Heartbeat]{Style.RESET_ALL} Install with: pip install plyer")
    
    def _send(self, title: str, message: str, tag: str = "heartbeat"):
        """
        Send a notification using the platform-appropriate backend.
        
        Args:
            title: Notification title
            message: Notification body text
            tag: Unique tag for this notification type (Windows only)
        """
        if BACKEND is None:
            return
        
        if BACKEND == "winotify":
            self._send_winotify(title, message, tag)
        elif BACKEND == "plyer":
            self._send_plyer(title, message)
    
    def _send_winotify(self, title: str, message: str, tag: str):
        """Send notification via winotify (Windows)."""
        toast = Notification(
            app_id=self.app_name,
            title=title,
            msg=message,
            duration=self.duration
        )
        
        if self.sound_enabled:
            toast.set_audio(audio.Default, loop=False)
        
        toast.show()
    
    def _send_plyer(self, title: str, message: str):
        """Send notification via plyer (macOS/Linux)."""
        try:
            plyer_notification.notify(
                title=title,
                message=message,
                app_name=self.app_name,
                timeout=self.timeout_seconds
            )
        except Exception:
            # plyer can fail on some systems without proper notification daemon
            pass
    
    def notify_chat_quiet(self, minutes: int, prompt: str):
        """
        Send a 'chat is quiet' notification.
        
        Args:
            minutes: How many minutes chat has been quiet
            prompt: Suggested conversation starter
        """
        title = f"Chat Quiet ({minutes} min)"
        message = f"Try: \"{prompt}\""
        
        self._send(title, message, tag="chat_quiet")
    
    def notify_viewer_return(
        self,
        username: str,
        days_ago: int,
        stream_count: int,
        prompt: str
    ):
        """
        Send a 'regular viewer returned' notification.
        
        Args:
            username: The viewer's username
            days_ago: Days since they were last seen
            stream_count: Total streams they've attended
            prompt: Suggested welcome message
        """
        title = f"{username} is back!"
        message = prompt
        
        self._send(title, message, tag=f"viewer_{username}")
    
    def notify_viewer_milestone(self, username: str, stream_count: int):
        """
        Send a 'viewer hit milestone' notification.
        
        Args:
            username: The viewer's username
            stream_count: The milestone they just hit
        """
        title = f"{username} - {stream_count} streams!"
        message = f"Celebrate their loyalty!"
        
        self._send(title, message, tag=f"milestone_{username}")
    
    def notify_raid(self, raider: str, viewer_count: int):
        """
        Send a raid notification.
        
        Args:
            raider: The raiding channel's name
            viewer_count: Number of viewers in the raid
        """
        title = f"RAID: {raider}"
        message = f"{viewer_count} viewers incoming!"
        
        self._send(title, message, tag="raid")
    
    def notify_subscription(
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
        Send a subscription notification.
        
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
        if sub_type == "sub":
            title = f"NEW SUB: {username}"
            message = f"{sub_plan}"
        
        elif sub_type == "resub":
            title = f"RESUB: {username}"
            streak_text = f" ({streak} mo streak)" if streak > 0 else ""
            message = f"{months} months - {sub_plan}{streak_text}"
        
        elif sub_type == "gift":
            title = f"GIFT: {gifter}"
            total_text = f" ({total_gifts} total)" if total_gifts > 0 else ""
            message = f"Gifted to {username} - {sub_plan}{total_text}"
        
        elif sub_type == "gift_bomb":
            title = f"GIFT BOMB: {gifter}"
            total_text = f" ({total_gifts} total)" if total_gifts > 0 else ""
            message = f"{gift_count}x {sub_plan} subs!{total_text}"
        
        elif sub_type == "prime_upgrade":
            title = f"UPGRADE: {username}"
            message = f"Prime to {sub_plan}"
        
        elif sub_type == "gift_upgrade":
            title = f"UPGRADE: {username}"
            from_text = f" (gift from {gifter})" if gifter else ""
            message = f"Continued sub{from_text} - {sub_plan}"
        
        else:
            title = f"SUB: {username or gifter}"
            message = sub_plan
        
        self._send(title, message, tag="subscription")
    
    def notify_streamer_quiet(self, minutes: int, prompt: str):
        """
        Send a 'streamer is quiet' notification.
        
        Note: This is for future use when Speaker.bot integration is added.
        
        Args:
            minutes: How many minutes the streamer has been quiet
            prompt: Suggested action
        """
        title = f"You've been quiet ({minutes} min)"
        message = prompt
        
        self._send(title, message, tag="streamer_quiet")
    
    def notify_custom(self, title: str, message: str):
        """
        Send a custom notification.
        
        For future extensibility or testing.
        
        Args:
            title: Notification title
            message: Notification body
        """
        self._send(title, message, tag="custom")
    
    def notify_watch_streak(self, username: str, streak_count: int):
        """
        Send a watch streak notification.
        
        Called when a viewer shares their Twitch watch streak.
        
        Args:
            username: The viewer's username
            streak_count: Their consecutive stream watch streak
        """
        title = f"STREAK: {username}"
        message = f"{streak_count} stream watch streak!"
        
        self._send(title, message, tag=f"streak_{username}")
