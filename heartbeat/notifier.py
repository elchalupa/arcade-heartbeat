"""
Windows toast notification system for arcade-heartbeat.

Uses winotify to display native Windows 10/11 toast notifications.
These appear in the corner of the screen and in the notification center.
"""

from winotify import Notification, audio


class Notifier:
    """
    Handles sending Windows toast notifications.
    
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
        
        # Icon path (could be customized later)
        self.icon_path = ""  # Empty string uses default Windows icon
    
    def _send(self, title: str, message: str, tag: str = "heartbeat"):
        """
        Send a toast notification.
        
        Args:
            title: Notification title
            message: Notification body text
            tag: Unique tag for this notification type (allows replacement)
        """
        toast = Notification(
            app_id=self.app_name,
            title=title,
            msg=message,
            duration=self.duration
        )
        
        # Set sound if enabled
        if self.sound_enabled:
            toast.set_audio(audio.Default, loop=False)
        
        # Show the notification
        toast.show()
    
    def notify_chat_quiet(self, minutes: int, prompt: str):
        """
        Send a 'chat is quiet' notification.
        
        Args:
            minutes: How many minutes chat has been quiet
            prompt: Suggested conversation starter
        """
        title = f"💬 Chat Quiet ({minutes} min)"
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
        title = f"👋 {username} is back!"
        message = prompt
        
        self._send(title, message, tag=f"viewer_{username}")
    
    def notify_streamer_quiet(self, minutes: int, prompt: str):
        """
        Send a 'streamer is quiet' notification.
        
        Note: This is for future use when Speaker.bot integration is added.
        
        Args:
            minutes: How many minutes the streamer has been quiet
            prompt: Suggested action
        """
        title = f"🎙️ You've been quiet ({minutes} min)"
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
