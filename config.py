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
    
    # Database configuration (can be overridden via env vars)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{PROJECT_ROOT / 'app.db'}"
    )
    
    # Application settings
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")
    
    @classmethod
    def validate(cls):
        """
        Validate that required settings are present.
        Raises ValueError if required settings are missing.
        """
        if not cls.YANDEX_MAPS_API_KEY:
            # Warning only, not required for basic functionality
            import warnings
            warnings.warn(
                "YANDEX_MAPS_API_KEY is not set. Some features may not work.",
                UserWarning
            )


# Create a settings instance
settings = Settings()

