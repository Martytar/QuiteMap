"""
Main FastAPI application for SSR (Server-Side Rendering) website.

This is a template project demonstrating how to create a multi-page website
using FastAPI with Jinja2 templates for server-side rendering.
"""

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path

# Database imports
from database import get_db, init_db
from models import User, Post

# Configuration imports
from config import settings

# Initialize FastAPI app
app = FastAPI(
    title="Hello World SSR",
    description="A template SSR website using FastAPI and uvicorn",
    version="1.0.0"
)

# Setup templates directory
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Mount static files directory (CSS, JS, images, etc.)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database tables on application startup."""
    # Validate configuration
    settings.validate()
    # Initialize database
    init_db()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    Home page - Hello, World!
    
    Example of a simple page route.
    """
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "Hello, World!",
            "message": "Welcome to your SSR website!",
            "yandex_maps_api_key": settings.YANDEX_MAPS_API_KEY
        }
    )

    
@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    """
    About page example.
    
    This demonstrates how to add additional pages to your website.
    """
    return templates.TemplateResponse(
        "about.html",
        {
            "request": request,
            "title": "About",
            "description": "This is an example about page."
        }
    )


@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    """
    Contact page example.
    
    Another example page showing how to add more routes.
    """
    return templates.TemplateResponse(
        "contact.html",
        {
            "request": request,
            "title": "Contact",
            "email": "hello@example.com"
        }
    )


# Example of a page with dynamic content
@app.get("/user/{username}", response_class=HTMLResponse)
async def user_profile(request: Request, username: str, db: Session = Depends(get_db)):
    """
    Dynamic route example with database integration.
    
    This shows how to create pages with dynamic parameters and database queries.
    """
    # Example ORM query: Get user from database
    user = db.query(User).filter(User.username == username).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user's posts
    posts = db.query(Post).filter(Post.author_id == user.id, Post.is_published == True).all()
    
    return templates.TemplateResponse(
        "user.html",
        {
            "request": request,
            "title": f"User: {username}",
            "username": username,
            "user": user,
            "posts": posts
        }
    )


# Example API endpoints demonstrating ORM operations
@app.get("/api/users", response_class=HTMLResponse)
async def list_users(request: Request, db: Session = Depends(get_db)):
    """
    Example page showing all users from database.
    
    Demonstrates:
    - Querying all records
    - Passing database results to templates
    """
    users = db.query(User).filter(User.is_active == True).all()
    
    return templates.TemplateResponse(
        "users_list.html",
        {
            "request": request,
            "title": "Users",
            "users": users
        }
    )


@app.get("/api/posts", response_class=HTMLResponse)
async def list_posts(request: Request, db: Session = Depends(get_db)):
    """
    Example page showing all published posts.
    
    Demonstrates:
    - Filtered queries
    - Ordering results
    """
    posts = db.query(Post).filter(Post.is_published == True).order_by(Post.created_at.desc()).all()
    
    return templates.TemplateResponse(
        "posts_list.html",
        {
            "request": request,
            "title": "Posts",
            "posts": posts
        }
    )


# Example of creating records (for demonstration - in production, use POST with forms)
@app.get("/api/create-example-data")
async def create_example_data(db: Session = Depends(get_db)):
    """
    Create example data in the database.
    
    This is a demonstration endpoint showing how to:
    - Create new records
    - Use database transactions
    - Handle errors
    """
    try:
        # Check if example user already exists
        existing_user = db.query(User).filter(User.username == "demo_user").first()
        if existing_user:
            return {"message": "Example data already exists", "user_id": existing_user.id}
        
        # Create a new user
        new_user = User(
            username="demo_user",
            email="demo@example.com",
            full_name="Demo User",
            is_active=True
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # Create a post for the user
        new_post = Post(
            title="Welcome to the SSR Template!",
            content="This is an example post created using SQLAlchemy ORM.",
            author_id=new_user.id,
            is_published=True
        )
        db.add(new_post)
        db.commit()
        
        return {
            "message": "Example data created successfully",
            "user_id": new_user.id,
            "post_id": new_post.id
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating example data: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

