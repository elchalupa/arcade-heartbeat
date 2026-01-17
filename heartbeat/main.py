"""
Main entry point for arcade-heartbeat.

This module initializes all components and starts the chat monitoring loop.
Run with: python -m heartbeat
"""

import asyncio
import os
import sys
import threading
from pathlib import Path

# Add colorama for Windows console colors
from colorama import init as colorama_init, Fore, Style

# Load environment variables from .env file
from dotenv import load_dotenv

# Keyboard listener for manual clear
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

# Import our modules
from heartbeat.config import load_config
from heartbeat.database import ViewerDatabase
from heartbeat.chat import HeartbeatBot, clear_console, print_cleared_banner
from heartbeat.engine import DecisionEngine
from heartbeat.notifier import Notifier
from heartbeat.prompts import PromptLibrary


def print_banner():
    """Display startup banner."""
    print(f"{Fore.MAGENTA}")
    print("  ╦ ╦┌─┐┌─┐┬─┐┌┬┐┌┐ ┌─┐┌─┐┌┬┐")
    print("  ╠═╣├┤ ├─┤├┬┘ │ ├┴┐├┤ ├─┤ │ ")
    print("  ╩ ╩└─┘┴ ┴┴└─ ┴ └─┘└─┘┴ ┴ ┴ ")
    print(f"{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}Stream Copilot v0.1.0{Style.RESET_ALL}")
    print()


def validate_environment():
    """Check that required environment variables are set."""
    required = ["TWITCH_ACCESS_TOKEN", "TWITCH_CHANNEL", "TWITCH_USERNAME"]
    missing = [var for var in required if not os.getenv(var)]
    
    if missing:
        print(f"{Fore.RED}[Error] Missing required environment variables:{Style.RESET_ALL}")
        for var in missing:
            print(f"  - {var}")
        print()
        print(f"Copy .env.example to .env and fill in your values.")
        sys.exit(1)


def setup_keyboard_listener():
    """Set up Ctrl+L hotkey for manual console clearing."""
    if not KEYBOARD_AVAILABLE:
        print(f"{Fore.YELLOW}[Heartbeat]{Style.RESET_ALL} Keyboard library not found, Ctrl+L disabled")
        print(f"{Fore.YELLOW}[Heartbeat]{Style.RESET_ALL} Install with: pip install keyboard")
        return
    
    def on_clear_hotkey():
        clear_console()
        print_cleared_banner()
    
    try:
        keyboard.add_hotkey('ctrl+l', on_clear_hotkey, suppress=True)
    except Exception as e:
        # Keyboard library may need admin rights on some systems
        print(f"{Fore.YELLOW}[Heartbeat]{Style.RESET_ALL} Could not register Ctrl+L hotkey: {e}")


def main():
    """Main entry point."""
    # Initialize colorama for Windows
    colorama_init()
    
    # Show banner
    print_banner()
    
    # Load .env file from current directory or project root
    env_path = Path(".env")
    if not env_path.exists():
        env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
    
    # Validate environment
    validate_environment()
    
    # Load configuration
    config_path = Path("config.yaml")
    if not config_path.exists():
        config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists():
        # Fall back to example config
        config_path = Path(__file__).parent.parent / "config.example.yaml"
    
    print(f"{Fore.CYAN}[Heartbeat]{Style.RESET_ALL} Loading configuration...")
    config = load_config(config_path)
    
    # Initialize database
    print(f"{Fore.CYAN}[Heartbeat]{Style.RESET_ALL} Initializing viewer database...")
    database = ViewerDatabase()
    viewer_count = database.get_viewer_count()
    print(f"{Fore.CYAN}[Heartbeat]{Style.RESET_ALL} Loaded {Fore.GREEN}{viewer_count}{Style.RESET_ALL} known viewers")
    
    # Initialize prompt library
    prompts_path = Path(config.get("prompts", {}).get("file", "prompts/default.yaml"))
    if not prompts_path.exists():
        prompts_path = Path(__file__).parent.parent / prompts_path
    print(f"{Fore.CYAN}[Heartbeat]{Style.RESET_ALL} Loading prompts from {prompts_path.name}...")
    prompts = PromptLibrary(prompts_path)
    
    # Initialize notifier
    notifier = Notifier(config)
    
    # Initialize decision engine
    engine = DecisionEngine(config, database, prompts, notifier)
    
    # Get Twitch credentials
    token = os.getenv("TWITCH_ACCESS_TOKEN")
    channel = os.getenv("TWITCH_CHANNEL")
    username = os.getenv("TWITCH_USERNAME")
    
    # Remove "oauth:" prefix if present (twitchio adds it)
    if token.startswith("oauth:"):
        token = token[6:]
    
    # Set up keyboard listener for Ctrl+L
    setup_keyboard_listener()
    
    # Initialize and run the bot
    print(f"{Fore.CYAN}[Heartbeat]{Style.RESET_ALL} Connecting to #{channel}...")
    print()
    
    bot = HeartbeatBot(
        token=token,
        channel=channel,
        username=username,
        config=config,
        engine=engine
    )
    
    # Run the bot
    try:
        bot.run()
    except KeyboardInterrupt:
        # twitchio may or may not catch this itself
        pass
    
    # Graceful shutdown
    print()
    print(f"{Fore.CYAN}[Heartbeat]{Style.RESET_ALL} Shutting down...")
    
    # Cancel the background monitoring task to prevent
    # "Task was destroyed but it is pending" warning
    if engine._monitoring_task and not bot.loop.is_closed():
        try:
            bot.loop.run_until_complete(engine.stop_monitoring())
        except Exception as e:
            if config.get("logging", {}).get("debug", False):
                print(f"{Fore.YELLOW}[Debug] Error stopping monitor: {e}{Style.RESET_ALL}")
    
    database.close()
    print(f"{Fore.CYAN}[Heartbeat]{Style.RESET_ALL} Goodbye!")


if __name__ == "__main__":
    main()
