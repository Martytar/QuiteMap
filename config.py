"""
Configuration management using environment variables.

Loads environment variables from .env and .env.local files.
.env.local takes precedence over .env for local development overrides.
"""

from pathlib import Path
from dotenv import load_dotenv
import os

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent

# Load .env file first (base configuration)
env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    load_dotenv(env_file)

# Load .env.local file second (local overrides, takes precedence)
env_local_file = PROJECT_ROOT / ".env.local"
if env_local_file.exists():
    load_dotenv(env_local_file, override=True)


class Settings:
    """
    Application settings loaded from environment variables.
    
    Access settings like: Settings.YANDEX_MAPS_API_KEY
    """
    
    # Yandex Maps API Key
    YANDEX_MAPS_API_KEY: str = os.getenv("YANDEX_MAPS_API_KEY", "")
    
    # Telegram Bot API Key
    TG_BOT_API_KEY: str = os.getenv("TG_BOT_API_KEY", "")
    
    # Telegram Bot Username (without @)
    TG_BOT_USERNAME: str = os.getenv("TG_BOT_USERNAME", "")
    
    # Application base URL for activation links
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")
    
    # Database configuration (can be overridden via env vars)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{PROJECT_ROOT / 'app.db'}"
    )
    
    # Application settings
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))


# Create a settings instance
settings = Settings()

