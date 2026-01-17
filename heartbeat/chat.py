"""
Twitch chat connection for arcade-heartbeat.

Uses twitchio to connect to Twitch IRC and monitor chat messages.
Forwards events to the decision engine for processing.
"""

import os
import sys
from datetime import datetime
from twitchio.ext import commands
from colorama import Fore, Style

from heartbeat.engine import DecisionEngine


# Colors for username assignment (readable on dark backgrounds)
USERNAME_COLORS = [
    Fore.CYAN,
    Fore.GREEN,
    Fore.YELLOW,
    Fore.MAGENTA,
    Fore.BLUE,
    Fore.RED,
    Fore.LIGHTCYAN_EX,
    Fore.LIGHTGREEN_EX,
    Fore.LIGHTYELLOW_EX,
    Fore.LIGHTMAGENTA_EX,
    Fore.LIGHTBLUE_EX,
    Fore.LIGHTRED_EX,
]


def get_username_color(username: str) -> str:
    """
    Get a consistent color for a username based on hash.
    
    Same username will always return the same color.
    
    Args:
        username: The username to colorize
        
    Returns:
        Colorama color code
    """
    # Use hash to pick a color index
    color_index = hash(username.lower()) % len(USERNAME_COLORS)
    return USERNAME_COLORS[color_index]


def clear_console():
    """Clear the console screen."""
    os.system('cls' if sys.platform == 'win32' else 'clear')
    

def print_cleared_banner():
    """Print a simple banner after clearing."""
    print(f"{Fore.CYAN}[Heartbeat]{Style.RESET_ALL} Console cleared")
    print(f"{Fore.CYAN}[Heartbeat]{Style.RESET_ALL} Monitoring chat... (Ctrl+C to stop, Ctrl+L to clear)")
    print()


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
        self.show_events = config.get("logging", {}).get("show_events", True)
        self.color_usernames = config.get("logging", {}).get("color_usernames", True)
        self.auto_clear_on_mod = config.get("safety", {}).get("auto_clear_on_mod_clear", True)
    
    async def event_ready(self):
        """Called when the bot successfully connects to Twitch."""
        print(f"{Fore.GREEN}[Heartbeat] Connected to #{self.channel_name}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}[Heartbeat]{Style.RESET_ALL} Monitoring chat... (Ctrl+C to stop, Ctrl+L to clear)")
        print()
        
        # Start the decision engine's background tasks
        self.loop.create_task(self.engine.start_monitoring())
    
    async def event_raw_data(self, data: str):
        """
        Called for all raw IRC messages.
        
        Used to catch CLEARCHAT events which aren't exposed via twitchio's
        standard event system.
        """
        # Check for CLEARCHAT (full chat clear, not targeted timeout/ban)
        if "CLEARCHAT" in data and self.auto_clear_on_mod:
            # Full clear has no target user, just the channel
            # Format: :tmi.twitch.tv CLEARCHAT #channel
            # Timeout/ban format: :tmi.twitch.tv CLEARCHAT #channel :username
            parts = data.strip().split(" ")
            
            # If there's no target (no 4th element or 4th element is empty after the channel)
            # then it's a full clear
            if len(parts) >= 3 and "CLEARCHAT" in parts[1]:
                # Check if there's a target user (would be after the channel)
                has_target = len(parts) > 3 and parts[3].startswith(":")
                
                if not has_target:
                    # Full chat clear by mod
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    clear_console()
                    print(f"{Fore.YELLOW}[{timestamp}]{Style.RESET_ALL} {Fore.RED}[MOD ACTION]{Style.RESET_ALL} Chat cleared by moderator")
                    print_cleared_banner()
    
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
            # Get color for this username
            user_color = get_username_color(author) if self.color_usernames else Fore.YELLOW
            print(f"{Fore.WHITE}[{timestamp}]{Style.RESET_ALL} {user_color}{author}{Style.RESET_ALL}: {content}")
        
        # Check if this is the streamer talking
        is_streamer = author.lower() == self.channel_name.lower()
        
        # Forward to decision engine
        await self.engine.on_message(
            username=author,
            content=content,
            is_streamer=is_streamer
        )
    
    async def event_raw_usernotice(self, channel, tags: dict):
        """
        Called for USERNOTICE events (raids, subs, gift subs, etc).
        
        These are special IRC messages that carry metadata about
        channel events in their tags.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        msg_id = tags.get("msg-id", "")
        
        # Handle raids
        if msg_id == "raid":
            raider = tags.get("display-name", tags.get("login", "Unknown"))
            viewer_count = int(tags.get("msg-param-viewerCount", 0))
            
            if self.show_events:
                raider_color = get_username_color(raider) if self.color_usernames else Fore.YELLOW
                print(f"{Fore.WHITE}[{timestamp}]{Style.RESET_ALL} {Fore.RED}[RAID]{Style.RESET_ALL} {raider_color}{raider}{Style.RESET_ALL} is raiding with {Fore.GREEN}{viewer_count}{Style.RESET_ALL} viewers!")
            
            await self.engine.on_raid(
                raider=raider,
                viewer_count=viewer_count
            )
        
        # Handle subscriptions
        elif msg_id == "sub":
            # New subscription
            subscriber = tags.get("display-name", tags.get("login", "Unknown"))
            sub_plan = self._parse_sub_plan(tags.get("msg-param-sub-plan", "1000"))
            
            if self.show_events:
                sub_color = get_username_color(subscriber) if self.color_usernames else Fore.YELLOW
                print(f"{Fore.WHITE}[{timestamp}]{Style.RESET_ALL} {Fore.MAGENTA}[SUB]{Style.RESET_ALL} {sub_color}{subscriber}{Style.RESET_ALL} subscribed! ({sub_plan})")
            
            await self.engine.on_subscription(
                username=subscriber,
                sub_type="sub",
                sub_plan=sub_plan,
                months=1,
                gifter=None,
                gift_count=None
            )
        
        elif msg_id == "resub":
            # Resubscription
            subscriber = tags.get("display-name", tags.get("login", "Unknown"))
            sub_plan = self._parse_sub_plan(tags.get("msg-param-sub-plan", "1000"))
            months = int(tags.get("msg-param-cumulative-months", 1))
            streak = int(tags.get("msg-param-streak-months", 0))
            
            if self.show_events:
                sub_color = get_username_color(subscriber) if self.color_usernames else Fore.YELLOW
                streak_text = f", {streak} month streak" if streak > 0 else ""
                print(f"{Fore.WHITE}[{timestamp}]{Style.RESET_ALL} {Fore.MAGENTA}[RESUB]{Style.RESET_ALL} {sub_color}{subscriber}{Style.RESET_ALL} resubscribed for {months} months ({sub_plan}{streak_text})")
            
            await self.engine.on_subscription(
                username=subscriber,
                sub_type="resub",
                sub_plan=sub_plan,
                months=months,
                gifter=None,
                gift_count=None,
                streak=streak
            )
        
        elif msg_id == "subgift":
            # Gift subscription (single)
            gifter = tags.get("display-name", tags.get("login", "Unknown"))
            recipient = tags.get("msg-param-recipient-display-name", 
                                tags.get("msg-param-recipient-user-name", "Unknown"))
            sub_plan = self._parse_sub_plan(tags.get("msg-param-sub-plan", "1000"))
            total_gifts = int(tags.get("msg-param-sender-count", 0))
            
            if self.show_events:
                gifter_color = get_username_color(gifter) if self.color_usernames else Fore.YELLOW
                recipient_color = get_username_color(recipient) if self.color_usernames else Fore.GREEN
                total_text = f" ({total_gifts} total)" if total_gifts > 0 else ""
                print(f"{Fore.WHITE}[{timestamp}]{Style.RESET_ALL} {Fore.MAGENTA}[GIFT]{Style.RESET_ALL} {gifter_color}{gifter}{Style.RESET_ALL} gifted a sub to {recipient_color}{recipient}{Style.RESET_ALL} ({sub_plan}){total_text}")
            
            await self.engine.on_subscription(
                username=recipient,
                sub_type="gift",
                sub_plan=sub_plan,
                months=1,
                gifter=gifter,
                gift_count=1,
                total_gifts=total_gifts
            )
        
        elif msg_id == "submysterygift":
            # Gift bomb (multiple random gifts)
            gifter = tags.get("display-name", tags.get("login", "Unknown"))
            gift_count = int(tags.get("msg-param-mass-gift-count", 1))
            sub_plan = self._parse_sub_plan(tags.get("msg-param-sub-plan", "1000"))
            total_gifts = int(tags.get("msg-param-sender-count", 0))
            
            if self.show_events:
                gifter_color = get_username_color(gifter) if self.color_usernames else Fore.YELLOW
                total_text = f" ({total_gifts} total)" if total_gifts > 0 else ""
                print(f"{Fore.WHITE}[{timestamp}]{Style.RESET_ALL} {Fore.MAGENTA}[GIFT BOMB]{Style.RESET_ALL} {gifter_color}{gifter}{Style.RESET_ALL} gifted {Fore.GREEN}{gift_count}{Style.RESET_ALL} subs! ({sub_plan}){total_text}")
            
            await self.engine.on_subscription(
                username=None,  # No specific recipient for gift bombs
                sub_type="gift_bomb",
                sub_plan=sub_plan,
                months=1,
                gifter=gifter,
                gift_count=gift_count,
                total_gifts=total_gifts
            )
        
        elif msg_id == "primepaidupgrade":
            # Prime to paid upgrade
            subscriber = tags.get("display-name", tags.get("login", "Unknown"))
            sub_plan = self._parse_sub_plan(tags.get("msg-param-sub-plan", "1000"))
            
            if self.show_events:
                sub_color = get_username_color(subscriber) if self.color_usernames else Fore.YELLOW
                print(f"{Fore.WHITE}[{timestamp}]{Style.RESET_ALL} {Fore.MAGENTA}[UPGRADE]{Style.RESET_ALL} {sub_color}{subscriber}{Style.RESET_ALL} upgraded from Prime ({sub_plan})")
            
            await self.engine.on_subscription(
                username=subscriber,
                sub_type="prime_upgrade",
                sub_plan=sub_plan,
                months=1,
                gifter=None,
                gift_count=None
            )
        
        elif msg_id == "giftpaidupgrade":
            # Gift to paid upgrade
            subscriber = tags.get("display-name", tags.get("login", "Unknown"))
            gifter = tags.get("msg-param-sender-name", tags.get("msg-param-sender-login", None))
            sub_plan = self._parse_sub_plan(tags.get("msg-param-sub-plan", "1000"))
            
            if self.show_events:
                sub_color = get_username_color(subscriber) if self.color_usernames else Fore.YELLOW
                gifter_text = f" (originally from {gifter})" if gifter else ""
                print(f"{Fore.WHITE}[{timestamp}]{Style.RESET_ALL} {Fore.MAGENTA}[UPGRADE]{Style.RESET_ALL} {sub_color}{subscriber}{Style.RESET_ALL} upgraded from gift sub{gifter_text} ({sub_plan})")
            
            await self.engine.on_subscription(
                username=subscriber,
                sub_type="gift_upgrade",
                sub_plan=sub_plan,
                months=1,
                gifter=gifter,
                gift_count=None
            )
        
        elif msg_id == "viewermilestone":
            # Twitch watch streak share
            viewer = tags.get("display-name", tags.get("login", "Unknown"))
            category = tags.get("msg-param-category", "watch-streak")
            value = tags.get("msg-param-value", "0")
            
            # Currently only watch-streak is supported by Twitch
            if category == "watch-streak":
                streak_count = int(value)
                
                if self.show_events:
                    viewer_color = get_username_color(viewer) if self.color_usernames else Fore.YELLOW
                    print(f"{Fore.WHITE}[{timestamp}]{Style.RESET_ALL} {Fore.CYAN}[STREAK]{Style.RESET_ALL} {viewer_color}{viewer}{Style.RESET_ALL} shared their {Fore.GREEN}{streak_count}{Style.RESET_ALL} stream watch streak!")
                
                await self.engine.on_watch_streak(
                    username=viewer,
                    streak_count=streak_count
                )
    
    def _parse_sub_plan(self, plan: str) -> str:
        """
        Convert Twitch sub plan code to readable string.
        
        Args:
            plan: Twitch plan code (Prime, 1000, 2000, 3000)
            
        Returns:
            Human-readable plan name
        """
        plans = {
            "Prime": "Prime",
            "1000": "Tier 1",
            "2000": "Tier 2",
            "3000": "Tier 3"
        }
        return plans.get(plan, plan)
    
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
