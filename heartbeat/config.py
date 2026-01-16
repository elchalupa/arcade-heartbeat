"""
Configuration loader for arcade-heartbeat.

Loads settings from config.yaml with sensible defaults.
"""

from pathlib import Path
from typing import Any
import yaml


# Default configuration values
DEFAULTS = {
    "thresholds": {
        "chat_quiet_minutes": 5,
        "regular_viewer_streams": 3,
        "regular_away_days": 2,
    },
    "cooldowns": {
        "chat_quiet_cooldown": 10,
        "viewer_welcome_cooldown": 0,
    },
    "notifications": {
        "sound": True,
        "app_name": "Heartbeat",
        "duration": "long",
    },
    "logging": {
        "show_chat": True,
        "debug": False,
    },
    "prompts": {
        "file": "prompts/default.yaml",
    },
}


def deep_merge(base: dict, override: dict) -> dict:
    """
    Recursively merge two dictionaries.
    Values in 'override' take precedence over 'base'.
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            result[key] = deep_merge(result[key], value)
        else:
            # Override the value
            result[key] = value
    
    return result


def load_config(config_path: Path = None) -> dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Falls back to defaults for any missing values.
    
    Args:
        config_path: Path to config.yaml file. If None, uses defaults only.
        
    Returns:
        Configuration dictionary with all settings.
    """
    config = DEFAULTS.copy()
    
    if config_path and config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
        
        # Merge user config with defaults
        config = deep_merge(DEFAULTS, user_config)
    
    return config


def get_threshold(config: dict, key: str) -> int:
    """Get a threshold value from config."""
    return config.get("thresholds", {}).get(key, DEFAULTS["thresholds"].get(key, 5))


def get_cooldown(config: dict, key: str) -> int:
    """Get a cooldown value from config."""
    return config.get("cooldowns", {}).get(key, DEFAULTS["cooldowns"].get(key, 10))
