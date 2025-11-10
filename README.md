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
├── templates/           # Jinja2 HTML templates
│   ├── base.html       # Base template with navigation
│   ├── index.html      # Home page
│   ├── about.html      # About page example
│   ├── contact.html    # Contact page example
│   └── user.html       # Dynamic route example
├── static/             # Static files (CSS, JS, images)
│   └── style.css       # Main stylesheet
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
uvicorn main:app --reload
```

### Using pip

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
uvicorn main:app --reload
```

The `--reload` flag enables auto-reload on code changes, perfect for development.

### Access the Website

Open your browser and navigate to:

- **Home**: http://localhost:8000/
- **About**: http://localhost:8000/about
- **Contact**: http://localhost:8000/contact
- **User Profile (example)**: http://localhost:8000/user/alice

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

- Use `uvicorn main:app --reload` for auto-reload during development
- Templates are automatically reloaded when changed
- Check the FastAPI docs at http://localhost:8000/docs for API documentation
- Use the interactive API explorer at http://localhost:8000/redoc

## Dependencies

- **FastAPI**: Modern web framework for building APIs and web apps
- **uvicorn**: ASGI server for running FastAPI applications
- **Jinja2**: Template engine for server-side rendering

## License

This is a template project - feel free to use it as a starting point for your own projects!
