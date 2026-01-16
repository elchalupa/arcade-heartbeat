"""
Prompt library for arcade-heartbeat.

Loads conversation starters and suggestions from a YAML file.
Supports variable substitution for personalized messages.
"""

import random
from pathlib import Path
from typing import Optional
import yaml


# Default prompts if no file is found
DEFAULT_PROMPTS = {
    "chat_quiet": [
        "What games has everyone been playing lately?",
        "Anyone have plans for the weekend?",
        "What brought you to the stream today?",
        "What's everyone up to?",
        "How's everyone's day going?",
        "Any recommendations for what I should play next?",
        "What are you all watching or playing besides this?",
        "Anyone here trying anything new lately?",
        "What's the last thing that made you laugh?",
        "Hot take time — what's an unpopular opinion you have?",
    ],
    "viewer_return": [
        "Welcome back {username}! (last seen {days_ago} days ago)",
        "{username} is here! They've been to {stream_count} streams",
        "Hey {username}! Good to see you again",
        "{username} just showed up — say hi!",
    ],
    "streamer_quiet": [
        "Chat might be waiting for you — check in!",
        "Good time to engage with chat",
        "Someone might feel ignored — take a peek",
        "Say something! Chat's been active",
    ],
}


class PromptLibrary:
    """
    Manages conversation prompts and suggestions.
    
    Prompts are loaded from a YAML file and can include placeholders
    like {username}, {days_ago}, and {stream_count} that get replaced
    with actual values when retrieved.
    """
    
    def __init__(self, prompts_path: Path = None):
        """
        Initialize the prompt library.
        
        Args:
            prompts_path: Path to prompts YAML file. Falls back to defaults if not found.
        """
        self.prompts = DEFAULT_PROMPTS.copy()
        
        if prompts_path and prompts_path.exists():
            try:
                with open(prompts_path, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f) or {}
                
                # Merge loaded prompts with defaults
                for key, value in loaded.items():
                    if isinstance(value, list) and value:
                        self.prompts[key] = value
            except Exception as e:
                print(f"Warning: Could not load prompts from {prompts_path}: {e}")
                print("Using default prompts.")
    
    def get_chat_quiet_prompt(self) -> str:
        """
        Get a random conversation starter for when chat is quiet.
        
        Returns:
            A suggested question or topic to engage chat.
        """
        prompts = self.prompts.get("chat_quiet", DEFAULT_PROMPTS["chat_quiet"])
        return random.choice(prompts)
    
    def get_viewer_return_prompt(
        self,
        username: str,
        days_ago: int,
        stream_count: int
    ) -> str:
        """
        Get a welcome-back message for a returning viewer.
        
        Args:
            username: The viewer's username
            days_ago: Days since they were last seen
            stream_count: Total streams they've attended
            
        Returns:
            A personalized welcome message.
        """
        prompts = self.prompts.get("viewer_return", DEFAULT_PROMPTS["viewer_return"])
        template = random.choice(prompts)
        
        # Replace placeholders
        return template.format(
            username=username,
            days_ago=days_ago,
            stream_count=stream_count
        )
    
    def get_streamer_quiet_prompt(self) -> str:
        """
        Get a reminder for when the streamer has been quiet.
        
        Note: For future use with Speaker.bot integration.
        
        Returns:
            A suggested action or reminder.
        """
        prompts = self.prompts.get("streamer_quiet", DEFAULT_PROMPTS["streamer_quiet"])
        return random.choice(prompts)
    
    def add_prompt(self, category: str, prompt: str):
        """
        Add a new prompt to a category.
        
        Args:
            category: The category (e.g., "chat_quiet", "viewer_return")
            prompt: The prompt text to add
        """
        if category not in self.prompts:
            self.prompts[category] = []
        
        if prompt not in self.prompts[category]:
            self.prompts[category].append(prompt)
    
    def get_all_prompts(self, category: str) -> list[str]:
        """
        Get all prompts in a category.
        
        Args:
            category: The category to retrieve
            
        Returns:
            List of prompt strings, or empty list if category not found.
        """
        return self.prompts.get(category, [])
