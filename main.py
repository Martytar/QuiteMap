from fastapi import FastAPI, Depends, Request, Form, HTTPException, status
from typing import Optional
import json
import httpx
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.sql import func
from database import Base, engine, get_db
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import secrets
from config import settings
from models import User, Place, Rating, Tag, place_tags

app = FastAPI(title="QuiteMap", description="Interactive Maps with Authentication")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

# Auth functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
):
    """Get current user from Bearer token or cookie"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = None
    
    # Try to get token from Bearer header
    if credentials:
        token = credentials.credentials
    # Try to get token from cookie
    if not token:
        token = request.cookies.get("access_token")
    
    if not token:
        raise credentials_exception
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

def get_user_from_token(request: Request, db: Session):
    token = request.cookies.get("access_token")
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username:
            user = db.query(User).filter(User.username == username).first()
            return user
    except JWTError:
        return None
    return None

# Routes
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: Session = Depends(get_db)):
    """Main page with login form"""
    user = get_user_from_token(request, db)
    if user:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Protected dashboard with maps"""
    user = get_user_from_token(request, db)
    if not user:
        return RedirectResponse(url="/")
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "yandex_maps_api_key": settings.YANDEX_MAPS_API_KEY,
    })

# Authentication routes
@app.post("/register")
async def register(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Register new user"""
    try:
        existing_user = db.query(User).filter(
            User.username == username
        ).first()
        
        if existing_user:
            return JSONResponse(
                status_code=400,
                content={"detail": "Username already registered"}
            )
        
        hashed_password = get_password_hash(password)
        user = User(
            username=username,
            hashed_password=hashed_password,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return {"message": "User created successfully", "user_id": user.id}
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Registration error: {str(e)}"}
        )

@app.post("/login")
async def login(
    response: JSONResponse,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Login user and return JWT token"""
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user or not verify_password(password, user.hashed_password):
            return JSONResponse(
                status_code=401,
                content={"detail": "Incorrect username or password"}
            )
        
        if not user.is_active:
            return JSONResponse(
                status_code=400,
                content={"detail": "Inactive user"}
            )
        
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        
        response = JSONResponse({
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user.id,
            "username": user.username
        })
        
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            expires=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        
        return response
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Login error: {str(e)}"}
        )

@app.post("/logout")
async def logout():
    """Logout user"""
    response = RedirectResponse(url="/")
    response.delete_cookie("access_token")
    return response

# Validation functions
def validate_hours_format(hours_list: list) -> tuple[bool, str]:
    """Validate hours format. Each hour should be in format 'HH-HH' or 'HH:MM-HH:MM'"""
    if not isinstance(hours_list, list):
        return False, "Hours must be a list"
    
    import re
    # Pattern: HH-HH or HH:MM-HH:MM (24-hour format)
    pattern = r'^([0-1]?[0-9]|2[0-3])(:([0-5][0-9]))?\-([0-1]?[0-9]|2[0-3])(:([0-5][0-9]))?$'
    
    for hour_range in hours_list:
        if not isinstance(hour_range, str):
            return False, f"Each hour range must be a string, got: {type(hour_range)}"
        if not re.match(pattern, hour_range.strip()):
            return False, f"Invalid hour format: '{hour_range}'. Expected format: '10-13' or '10:00-13:00'"
    
    return True, ""

def validate_rating(rating: float) -> tuple[bool, str]:
    """Validate rating is between 0.0 and 5.0"""
    if not isinstance(rating, (int, float)):
        return False, "Rating must be a number"
    if rating < 0.0 or rating > 5.0:
        return False, "Rating must be between 0.0 and 5.0"
    return True, ""

def validate_noise_level(noise_level: int) -> tuple[bool, str]:
    """Validate noise level is between 1 and 4"""
    if not isinstance(noise_level, int):
        return False, "Noise level must be an integer"
    if noise_level < 1 or noise_level > 4:
        return False, "Noise level must be between 1 and 4"
    return True, ""

def validate_coordinates(latitude: float, longitude: float) -> tuple[bool, str]:
    """Validate coordinates are within valid ranges"""
    if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
        return False, "Coordinates must be numbers"
    if latitude < -90 or latitude > 90:
        return False, "Latitude must be between -90 and 90"
    if longitude < -180 or longitude > 180:
        return False, "Longitude must be between -180 and 180"
    return True, ""

async def reverse_geocode(latitude: float, longitude: float) -> str:
    """Get address from coordinates using Yandex Geocoder API"""
    try:
        api_key = settings.YANDEX_MAPS_API_KEY
        if not api_key:
            return ""
        
        async with httpx.AsyncClient() as client:
            url = f"https://geocode-maps.yandex.ru/1.x/"
            params = {
                "apikey": api_key,
                "geocode": f"{longitude},{latitude}",
                "format": "json",
                "results": 1
            }
            response = await client.get(url, params=params)
            data = response.json()
            
            if data.get("response", {}).get("GeoObjectCollection", {}).get("featureMember"):
                geo_object = data["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]
                return geo_object.get("metaDataProperty", {}).get("GeocoderMetaData", {}).get("text", "")
    except Exception as e:
        print(f"Geocoding error: {e}")
    return ""

# Places API endpoints
@app.get("/api/places")
async def get_places(request: Request, db: Session = Depends(get_db)):
    """Get all places (available to all users)"""
    try:
        places = db.query(Place).all()
        places_data = []
        for place in places:
            # Get address from geocoder if not cached
            address = place.address
            if not address:
                address = await reverse_geocode(place.latitude, place.longitude)
                if address:
                    place.address = address
                    db.commit()
            
            # Calculate average rating from ratings table
            avg_rating_result = db.query(func.avg(Rating.rating)).filter(
                Rating.place_id == place.id
            ).scalar()
            avg_rating = float(avg_rating_result) if avg_rating_result else 0.0
            
            # Get tags from relationship
            tag_names = [tag.name for tag in place.tags]
            
            places_data.append({
                "id": place.id,
                "latitude": place.latitude,
                "longitude": place.longitude,
                "name": place.name,
                "noise_level": place.noise_level,
                "amenities": json.loads(place.amenities) if place.amenities else [],
                "tags": tag_names,
                "rating": round(avg_rating, 1),
                "hours": json.loads(place.hours) if place.hours else [],
                "address": address or ""
            })
        return {"places": places_data}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error loading places: {str(e)}"}
        )

@app.post("/api/places")
async def create_place(
    request: Request,
    latitude: float = Form(...),
    longitude: float = Form(...),
    name: str = Form(...),
    noise_level: int = Form(1),
    amenities: str = Form("[]"),
    tags: str = Form("[]"),
    hours: str = Form("[]"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new place"""
    try:
        # Validate coordinates
        valid, error = validate_coordinates(latitude, longitude)
        if not valid:
            return JSONResponse(status_code=400, content={"detail": error})
        
        # Validate noise level
        valid, error = validate_noise_level(noise_level)
        if not valid:
            return JSONResponse(status_code=400, content={"detail": error})
        
        # Validate name
        name = name.strip()
        if not name or len(name) > 200:
            return JSONResponse(
                status_code=400,
                content={"detail": "Name is required and must be 200 characters or less"}
            )
        
        # Validate and parse hours
        try:
            hours_list = json.loads(hours) if hours else []
            if not isinstance(hours_list, list):
                hours_list = []
        except (json.JSONDecodeError, TypeError):
            return JSONResponse(
                status_code=400,
                content={"detail": "Hours must be a valid JSON array"}
            )
        
        valid, error = validate_hours_format(hours_list)
        if not valid:
            return JSONResponse(status_code=400, content={"detail": error})
        
        # Validate and parse amenities
        try:
            amenities_list = json.loads(amenities) if amenities else []
            if not isinstance(amenities_list, list):
                amenities_list = []
            # Validate amenities are strings
            for amenity in amenities_list:
                if not isinstance(amenity, str):
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "All amenities must be strings"}
                    )
        except (json.JSONDecodeError, TypeError):
            return JSONResponse(
                status_code=400,
                content={"detail": "Amenities must be a valid JSON array"}
            )
        
        # Validate and parse tags
        try:
            tags_list = json.loads(tags) if tags else []
            if not isinstance(tags_list, list):
                tags_list = []
            # Validate tags are strings and trim them
            tag_names = []
            for tag in tags_list:
                if not isinstance(tag, str):
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "All tags must be strings"}
                    )
                tag_trimmed = tag.strip()
                if tag_trimmed and len(tag_trimmed) <= 100:
                    tag_names.append(tag_trimmed)
        except (json.JSONDecodeError, TypeError):
            return JSONResponse(
                status_code=400,
                content={"detail": "Tags must be a valid JSON array"}
            )
        
        # Get address from geocoder
        address = await reverse_geocode(latitude, longitude)
        
        # Create place
        place = Place(
            user_id=user.id,
            latitude=latitude,
            longitude=longitude,
            name=name,
            noise_level=noise_level,
            amenities=json.dumps(amenities_list),
            hours=json.dumps(hours_list),
            address=address
        )
        db.add(place)
        db.flush()  # Flush to get place.id
        
        # Create or get tags and associate with place
        for tag_name in tag_names:
            # Get or create tag
            tag = db.query(Tag).filter(Tag.name == tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                db.add(tag)
                db.flush()
            place.tags.append(tag)
        
        db.commit()
        db.refresh(place)
        
        return {
            "id": place.id,
            "message": "Place created successfully",
            "address": address
        }
    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error creating place: {str(e)}"}
        )

@app.delete("/api/places/{place_id}")
async def delete_place(
    place_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a place"""
    try:
        place = db.query(Place).filter(Place.id == place_id, Place.user_id == user.id).first()
        if not place:
            return JSONResponse(
                status_code=404,
                content={"detail": "Place not found"}
            )
        db.delete(place)
        db.commit()
        return {"message": "Place deleted successfully"}
    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error deleting place: {str(e)}"}
        )

@app.post("/api/places/{place_id}/rating")
async def rate_place(
    place_id: int,
    rating: float = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Rate a place (create or update rating)"""
    try:
        # Validate rating value
        valid, error = validate_rating(rating)
        if not valid:
            return JSONResponse(status_code=400, content={"detail": error})
        
        # Check if place exists
        place = db.query(Place).filter(Place.id == place_id).first()
        if not place:
            return JSONResponse(
                status_code=404,
                content={"detail": "Place not found"}
            )
        
        # Check if user already rated this place
        existing_rating = db.query(Rating).filter(
            Rating.place_id == place_id,
            Rating.user_id == user.id
        ).first()
        
        if existing_rating:
            # Update existing rating
            existing_rating.rating = rating
            existing_rating.updated_at = datetime.now(timezone.utc)
        else:
            # Create new rating
            new_rating = Rating(
                user_id=user.id,
                place_id=place_id,
                rating=rating
            )
            db.add(new_rating)
        
        db.commit()
        
        # Calculate new average rating
        avg_rating_result = db.query(func.avg(Rating.rating)).filter(
            Rating.place_id == place_id
        ).scalar()
        avg_rating = float(avg_rating_result) if avg_rating_result else 0.0
        
        return {
            "message": "Rating saved successfully",
            "average_rating": round(avg_rating, 1)
        }
    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error saving rating: {str(e)}"}
        )

@app.get("/api/places/{place_id}/rating")
async def get_user_rating(
    place_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's rating for a place"""
    try:
        rating = db.query(Rating).filter(
            Rating.place_id == place_id,
            Rating.user_id == user.id
        ).first()
        
        if rating:
            return {"rating": rating.rating}
        else:
            return {"rating": None}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error getting rating: {str(e)}"}
        )

@app.get("/api/tags/autocomplete")
async def autocomplete_tags(
    q: str = "",
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get tag suggestions for autocomplete"""
    try:
        query = q.strip()
        if not query:
            # Return most used tags if no query
            tags = db.query(Tag).join(place_tags).group_by(Tag.id).order_by(
                func.count(place_tags.c.place_id).desc()
            ).limit(limit).all()
        else:
            # Search tags by name (SQLite compatible - use LIKE with lower)
            query_lower = query.lower()
            tags = db.query(Tag).filter(
                func.lower(Tag.name).like(f"%{query_lower}%")
            ).order_by(Tag.name).limit(limit).all()
        
        return {"tags": [tag.name for tag in tags]}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error getting tags: {str(e)}"}
        )

# Initialize application
@app.on_event("startup")
async def startup_event():
    """Initialize application"""
    print("QuiteMap application started")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully")
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
