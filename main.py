"""
Main FastAPI application for SSR (Server-Side Rendering) website.

This is a template project demonstrating how to create a multi-page website
using FastAPI with Jinja2 templates for server-side rendering.
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

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
            "message": "Welcome to your SSR website!"
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
async def user_profile(request: Request, username: str):
    """
    Dynamic route example.
    
    This shows how to create pages with dynamic parameters.
    """
    return templates.TemplateResponse(
        "user.html",
        {
            "request": request,
            "title": f"User: {username}",
            "username": username
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

