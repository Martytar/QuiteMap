# Environment Variables Guide

This project uses environment variables for configuration. Environment variables are loaded from `.env` and `.env.local` files.

## File Structure

- **`.env`** - Base configuration file (tracked in git)
- **`.env.local`** - Local overrides (not tracked in git, for secrets)
- **`.env.local.example`** - Example template for local configuration

## Setup

1. **Create `.env` file** (if not exists):
   ```bash
   # Yandex Maps API Key
   YANDEX_MAPS_API_KEY=your-api-key-here
   ```

2. **Create `.env.local` file** for local development:
   ```bash
   cp .env.local.example .env.local
   # Then edit .env.local with your actual API keys
   ```

## Available Variables

### YANDEX_MAPS_API_KEY

**Required**: Yandex Maps API key for map functionality.

- Get your API key from: https://developer.tech.yandex.com/
- Set in `.env` or `.env.local`

### DATABASE_URL (Optional)

Database connection string. Defaults to SQLite if not set.

```bash
DATABASE_URL=sqlite:///./app.db
# Or for PostgreSQL:
# DATABASE_URL=postgresql://user:password@localhost/dbname
```

### DEBUG (Optional)

Enable debug mode. Defaults to `False`.

```bash
DEBUG=True
```

### SECRET_KEY (Optional)

Secret key for session management, JWT tokens, etc. Defaults to a placeholder.

```bash
SECRET_KEY=your-secret-key-here
```

## Usage in Code

Access environment variables through the `settings` object:

```python
from config import settings

# Get Yandex Maps API Key
api_key = settings.YANDEX_MAPS_API_KEY

# Check if API key is set
if settings.YANDEX_MAPS_API_KEY:
    # Use the API key
    pass
else:
    # Handle missing API key
    pass
```

## Precedence

`.env.local` takes precedence over `.env`. This allows you to:
- Keep `.env` with default/example values in git
- Override with actual secrets in `.env.local` (not tracked in git)

## Security Best Practices

1. **Never commit `.env.local`** - It contains your actual secrets
2. **Use `.env.local.example`** - Document required variables without exposing secrets
3. **Rotate API keys** - If a key is compromised, generate a new one
4. **Use different keys** - Use separate keys for development and production

## Production Deployment

For production, set environment variables through your hosting platform:

- **Heroku**: `heroku config:set YANDEX_MAPS_API_KEY=your-key`
- **Docker**: Use `-e` flag or docker-compose `environment` section
- **Systemd**: Set in service file `Environment` directive
- **Cloud platforms**: Use their secrets/environment variable management

Do not commit production secrets to git!

