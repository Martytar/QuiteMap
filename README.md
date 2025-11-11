# Hello World SSR - FastAPI Template

A clean, well-structured template for building Server-Side Rendered (SSR) websites using Python, FastAPI, and uvicorn.

## Features

- 🚀 Fast and efficient with uvicorn ASGI server
- 📄 Server-side rendering with Jinja2 templates
- 🎨 Modern, responsive CSS styling
- 📝 Well-documented code with examples
- 🔧 Easy to extend with new pages

## Project Structure

```
QuiteMap/
├── main.py              # Main FastAPI application
├── database.py          # Database configuration and session management
├── models.py            # SQLAlchemy ORM models
├── config.py            # Environment variable configuration
├── .env                 # Environment variables (base config)
├── .env.local.example   # Example local environment file
├── templates/           # Jinja2 HTML templates
│   ├── base.html       # Base template with navigation
│   ├── index.html      # Home page
│   ├── about.html      # About page example
│   ├── contact.html    # Contact page example
│   ├── user.html       # Dynamic route example
│   ├── users_list.html # Users listing page
│   └── posts_list.html # Posts listing page
├── static/             # Static files (CSS, JS, images)
│   └── style.css       # Main stylesheet
├── alembic/            # Database migrations
│   ├── versions/       # Migration scripts
│   ├── env.py          # Alembic environment configuration
│   └── script.py.mako  # Migration template
├── alembic.ini         # Alembic configuration
├── app.db              # SQLite database (created on first run)
├── requirements.txt    # Python dependencies
├── shell.nix          # Nix development environment
└── README.md          # This file
```

## Getting Started

### Using Nix (Recommended)

If you have Nix installed, simply enter the development shell:

```bash
nix-shell
```

Then run the application:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Using pip

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The `--reload` flag enables auto-reload on code changes, perfect for development.

### Environment Variables

This project uses `.env` and `.env.local` files for configuration. Create these files in the project root:

**`.env`** - Base configuration (tracked in git):
```bash
# Yandex Maps API Key
YANDEX_MAPS_API_KEY=your-api-key-here

# Database configuration (optional)
# DATABASE_URL=sqlite:///./app.db

# Application settings
# DEBUG=False
# SECRET_KEY=change-this-secret-key-in-production
```

**`.env.local`** - Local overrides (not tracked in git):
```bash
# Copy from .env.local.example and set your actual values
YANDEX_MAPS_API_KEY=your-actual-api-key-here
```

The `.env.local` file takes precedence over `.env` for local development. Create `.env.local` by copying `.env.local.example`:

```bash
cp .env.local.example .env.local
# Then edit .env.local with your actual API keys
```

**Get Yandex Maps API Key**: https://developer.tech.yandex.com/

### Access the Website

Open your browser and navigate to:

- **Home**: http://localhost:8000/ (or http://your-server-ip:8000/ if accessing remotely)
- **About**: http://localhost:8000/about
- **Contact**: http://localhost:8000/contact
- **Users List**: http://localhost:8000/api/users
- **Posts List**: http://localhost:8000/api/posts
- **Create Example Data**: http://localhost:8000/api/create-example-data
- **User Profile (example)**: http://localhost:8000/user/demo_user (after creating example data)

## How to Add New Pages

### Step 1: Add a Route in `main.py`

Add a new route handler function:

```python
@app.get("/your-page", response_class=HTMLResponse)
async def your_page(request: Request):
    return templates.TemplateResponse(
        "your_page.html",
        {
            "request": request,
            "title": "Your Page Title",
            "custom_data": "Any data you want to pass to the template"
        }
    )
```

### Step 2: Create a Template

Create a new file in `templates/your_page.html`:

```jinja2
{% extends "base.html" %}

{% block content %}
<h1>{{ title }}</h1>
<p>Your content here. You can use {{ custom_data }} in your template.</p>
{% endblock %}
```

### Step 3: Update Navigation (Optional)

Add a link in `templates/base.html` in the navigation section:

```html
<li><a href="/your-page">Your Page</a></li>
```

## Dynamic Routes

You can create dynamic routes using path parameters:

```python
@app.get("/product/{product_id}", response_class=HTMLResponse)
async def product_page(request: Request, product_id: int):
    return templates.TemplateResponse(
        "product.html",
        {
            "request": request,
            "title": f"Product {product_id}",
            "product_id": product_id
        }
    )
```

Then access it at `/product/123` or `/product/456`.

## Template Inheritance

All pages extend `base.html`, which provides:
- Consistent navigation
- Footer
- Base styling
- HTML structure

Use the `{% block content %}` block to add page-specific content.

## Static Files

Place CSS, JavaScript, and images in the `static/` directory. They will be automatically served at `/static/...`.

Reference them in templates:

```jinja2
<link rel="stylesheet" href="{{ url_for('static', path='/style.css') }}">
```

## Development Tips

- Use `uvicorn main:app --host 0.0.0.0 --port 8000 --reload` for auto-reload during development
- Templates are automatically reloaded when changed
- Check the FastAPI docs at http://localhost:8000/docs for API documentation
- Use the interactive API explorer at http://localhost:8000/redoc

## Database & ORM

This project uses **SQLAlchemy** as the ORM and **SQLite3** as the database.

### Database Models

Example models are defined in `models.py`:
- **User**: User accounts with username, email, and profile information
- **Post**: Blog posts with title, content, and author relationship

### Using the Database

The database is automatically initialized when the application starts. Example ORM operations:

```python
from database import get_db
from models import User, Post
from sqlalchemy.orm import Session

@app.get("/users")
async def get_users(db: Session = Depends(get_db)):
    # Query all active users
    users = db.query(User).filter(User.is_active == True).all()
    return users

@app.post("/users")
async def create_user(db: Session = Depends(get_db)):
    # Create a new user
    new_user = User(
        username="john_doe",
        email="john@example.com",
        full_name="John Doe"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
```

### Database Migrations with Alembic

This project includes Alembic for database migrations.

#### Initial Setup

After installing dependencies, initialize Alembic (already done, but for reference):

```bash
alembic init alembic
```

#### Creating Migrations

When you modify models in `models.py`, create a new migration:

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Description of changes"

# Or create an empty migration for manual edits
alembic revision -m "Description of changes"
```

#### Applying Migrations

Apply all pending migrations:

```bash
alembic upgrade head
```

#### Rolling Back Migrations

Roll back one migration:

```bash
alembic downgrade -1
```

Roll back to a specific revision:

```bash
alembic downgrade <revision_id>
```

#### View Migration History

```bash
alembic history
```

#### Example Workflow

1. Modify `models.py` (add a field, create a new model, etc.)
2. Generate migration: `alembic revision --autogenerate -m "Add user avatar field"`
3. Review the generated migration in `alembic/versions/`
4. Apply migration: `alembic upgrade head`

**Note**: The database is automatically created on first run using `init_db()`. For production, use migrations instead.

## Environment Variables

Access environment variables in your code using the `settings` object:

```python
from config import settings

# Access Yandex Maps API Key
api_key = settings.YANDEX_MAPS_API_KEY

# Access other settings
debug_mode = settings.DEBUG
secret_key = settings.SECRET_KEY
```

The `config.py` module automatically loads variables from `.env` and `.env.local` files (`.env.local` takes precedence).

## Dependencies

- **FastAPI**: Modern web framework for building APIs and web apps
- **uvicorn**: ASGI server for running FastAPI applications
- **Jinja2**: Template engine for server-side rendering
- **SQLAlchemy**: SQL toolkit and ORM for Python
- **Alembic**: Database migration tool for SQLAlchemy
- **python-dotenv**: Environment variable management from .env files

## License

This is a template project - feel free to use it as a starting point for your own projects!
