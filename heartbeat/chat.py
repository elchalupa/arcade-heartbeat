"""
Twitch chat connection for arcade-heartbeat.

Uses twitchio to connect to Twitch IRC and monitor chat messages.
Forwards events to the decision engine for processing.
"""

from datetime import datetime
from twitchio.ext import commands
from colorama import Fore, Style

from heartbeat.engine import DecisionEngine


class HeartbeatBot(commands.Bot):
    """
    Twitch chat bot that monitors messages and forwards to the decision engine.
    
    This bot is read-only by design — it never sends messages to chat.
    All actions are notifications to the streamer.
    """
    
    def __init__(
        self,
        token: str,
        channel: str,
        username: str,
        config: dict,
        engine: DecisionEngine
    ):
        """
        Initialize the Twitch bot.
        
        Args:
            token: Twitch OAuth token (without "oauth:" prefix)
            channel: Channel name to join (without #)
            username: Bot's username (account that owns the token)
            config: Configuration dictionary
            engine: Decision engine instance for processing events
        """
        # Initialize the bot with our token
        super().__init__(
            token=token,
            prefix="!",  # Not used, but required by twitchio
            initial_channels=[channel]
        )
        
        self.channel_name = channel.lower()
        self.username = username.lower()
        self.config = config
        self.engine = engine
        self.show_chat = config.get("logging", {}).get("show_chat", True)
    
    async def event_ready(self):
        """Called when the bot successfully connects to Twitch."""
        print(f"{Fore.GREEN}[Heartbeat] Connected to #{self.channel_name}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}[Heartbeat]{Style.RESET_ALL} Monitoring chat... (Ctrl+C to stop)")
        print()
        
        # Start the decision engine's background tasks
        self.loop.create_task(self.engine.start_monitoring())
    
    async def event_message(self, message):
        """
        Called for every chat message.
        
        This is the heart of the monitoring system. Each message is:
        1. Logged to console (if enabled)
        2. Forwarded to the decision engine
        3. Used to update chat activity timestamps
        """
        # Ignore messages from the bot itself
        if message.echo:
            return
        
        # Get message details
        author = message.author.name if message.author else "unknown"
        content = message.content
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Log to console if enabled
        if self.show_chat:
            # Color the username for visibility
            print(f"{Fore.WHITE}[{timestamp}]{Style.RESET_ALL} {Fore.YELLOW}{author}{Style.RESET_ALL}: {content}")
        
        # Check if this is the streamer talking
        is_streamer = author.lower() == self.channel_name.lower()
        
        # Forward to decision engine
        await self.engine.on_message(
            username=author,
            content=content,
            is_streamer=is_streamer
        )
    
    async def event_join(self, channel, user):
        """Called when a user joins the channel."""
        # We don't track joins currently, but this is here for future use
        # Most joins are invisible unless the user chats
        pass
    
    async def event_part(self, user):
        """Called when a user leaves the channel."""
        # We don't track parts currently
        pass
    
    async def event_error(self, error: Exception, data: str = None):
        """Called when an error occurs."""
        print(f"{Fore.RED}[Error] {error}{Style.RESET_ALL}")
        if data:
            print(f"{Fore.RED}  Data: {data}{Style.RESET_ALL}")
