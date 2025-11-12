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
from models import User, Place, Rating, Tag, place_tags, PendingRegistration

app = FastAPI(title="QuiteMap", description="Interactive Maps with Authentication")

# Middleware to add cache headers for static files
@app.middleware("http")
async def add_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static"):
        # Cache static files for 1 hour (3600 seconds)
        response.headers["Cache-Control"] = "public, max-age=3600, immutable"
    return response

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
        return RedirectResponse(url="/map")
    return templates.TemplateResponse("index.html", {
        "request": request,
        "tg_bot_username": settings.TG_BOT_USERNAME or "quite_map_register_bot",
        "base_url": settings.BASE_URL
    })

@app.get("/map", response_class=HTMLResponse)
async def map(request: Request, db: Session = Depends(get_db)):
    user = get_user_from_token(request, db)
    if not user:
        return RedirectResponse(url="/")
    
    return templates.TemplateResponse("map.html", {
        "request": request,
        "user": user,
        "yandex_maps_api_key": settings.YANDEX_MAPS_API_KEY,
    })

# Authentication routes
@app.post("/register")
async def register(
    username: str = Form(...),
    telegram_handle: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Create pending registration - user will confirm via Telegram bot"""
    try:
        # Normalize inputs
        username = username.strip()
        telegram_handle = telegram_handle.lstrip('@').strip()
        password = password.strip()
        
        # Validate inputs
        if not username or len(username) < 3:
            return JSONResponse(
                status_code=400,
                content={"detail": "Username must be at least 3 characters"}
            )
        
        if len(username) > 50:
            return JSONResponse(
                status_code=400,
                content={"detail": "Username must be 50 characters or less"}
            )
        
        if not telegram_handle:
            return JSONResponse(
                status_code=400,
                content={"detail": "Telegram handle is required"}
            )
        
        if not password or len(password) < 6:
            return JSONResponse(
                status_code=400,
                content={"detail": "Password must be at least 6 characters"}
            )
        
        # Check if username already exists
        existing_user_by_username = db.query(User).filter(
            User.username == username
        ).first()
        
        if existing_user_by_username:
            return JSONResponse(
                status_code=400,
                content={"detail": "Username already registered"}
            )
        
        # Check if telegram handle already exists
        existing_user_by_handle = db.query(User).filter(
            User.telegram_handle == telegram_handle
        ).first()
        
        if existing_user_by_handle:
            return JSONResponse(
                status_code=400,
                content={"detail": "This Telegram handle is already registered"}
            )
        
        # Check if there's already a pending registration for this telegram handle
        existing_pending = db.query(PendingRegistration).filter(
            PendingRegistration.telegram_handle == telegram_handle
        ).first()
        
        if existing_pending:
            # Check if expired - ensure timezone-aware comparison
            expires_at = existing_pending.expires_at
            if expires_at.tzinfo is None:
                # Make timezone-aware if naive (SQLite issue)
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            
            if expires_at < datetime.now(timezone.utc):
                db.delete(existing_pending)
                db.commit()
            else:
                # Update existing pending registration with new data
                existing_pending.username = username
                existing_pending.hashed_password = get_password_hash(password)
                db.commit()
                bot_username = settings.TG_BOT_USERNAME or "quite_map_register_bot"
                return {
                    "message": f"Registration request updated. Please go to Telegram bot @{bot_username} and use /start or /activate."
                }
        
        # Hash password
        hashed_password = get_password_hash(password)
        
        # Generate confirmation token
        confirmation_token = secrets.token_urlsafe(32)
        
        # Create pending registration (expires in 1 hour)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        pending_reg = PendingRegistration(
            username=username,
            telegram_handle=telegram_handle,
            hashed_password=hashed_password,
            confirmation_token=confirmation_token,
            expires_at=expires_at
        )
        
        db.add(pending_reg)
        db.commit()
        db.refresh(pending_reg)
        
        bot_username = settings.TG_BOT_USERNAME or "quite_map_register_bot"
        return {
            "message": f"Registration request created. Please go to Telegram bot @{bot_username} and use /start or /activate."
        }
    
    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"detail": f"Registration error: {str(e)}"}
        )

@app.get("/activate/{token}")
async def activate_account(
    token: str,
    db: Session = Depends(get_db)
):
    """Activate user account using activation token"""
    try:
        user = db.query(User).filter(User.activation_token == token).first()
        
        if not user:
            return JSONResponse(
                status_code=404,
                content={"detail": "Invalid or expired activation token"}
            )
        
        if user.is_active:
            return JSONResponse(
                status_code=400,
                content={"detail": "Account is already activated"}
            )
        
        # Activate user and clear token
        user.is_active = True
        user.activation_token = None
        db.commit()
        
        return HTMLResponse(
            content=f"""
            <html>
                <head><title>Account Activated</title></head>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h1>Account Activated Successfully!</h1>
                    <p>Your account <strong>{user.username}</strong> has been activated.</p>
                    <p><a href="/">Click here to login</a></p>
                </body>
            </html>
            """
        )
    
    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"detail": f"Activation error: {str(e)}"}
        )

@app.post("/login")
async def login(
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
    """Validate hours format. Each hour should be in format 'HH-HH' or 'HH:MM-HH:MM'.
    Normalizes single-digit hours to two digits (e.g., '0-24' -> '00-24').
    Validates that left side is less than or equal to right side."""
    if not isinstance(hours_list, list):
        return False, "Hours must be a list"
    
    import re
    # allows "HH-HH", "HH:MM-HH:MM" and also "24" or "24:00"
    pattern = r'^(?:([01]?\d|2[0-3])(?::([0-5][0-9]))?|24(?::00)?)\-(?:([01]?\d|2[0-3])(?::([0-5][0-9]))?|24(?::00)?)$'
    
    def normalize_time(time_str: str) -> str:
        """Normalize time string: '0' -> '00', '5' -> '05', etc."""
        if ':' in time_str:
            hour, minute = time_str.split(':')
            return f"{int(hour):02d}:{minute}"
        else:
            return f"{int(time_str):02d}"
    
    def time_to_minutes(time_str: str) -> int:
        """Convert time string to minutes since midnight for comparison."""
        if time_str == '24' or time_str == '24:00':
            return 24 * 60  # 1440 minutes
        if ':' in time_str:
            parts = time_str.split(':')
            hour = int(parts[0])
            minute = int(parts[1])
            return hour * 60 + minute
        else:
            return int(time_str) * 60
    
    for i, hour_range in enumerate(hours_list):
        if not isinstance(hour_range, str):
            return False, f"Each hour range must be a string, got: {type(hour_range)}"
        
        hour_range = hour_range.strip()
        if not re.match(pattern, hour_range):
            return False, f"Invalid hour format: '{hour_range}'. Expected format: '10-13' or '10:00-13:00'"
        
        # Split into start and end times
        parts = hour_range.split('-')
        if len(parts) != 2:
            return False, f"Invalid hour format: '{hour_range}'. Expected format: 'HH-HH' or 'HH:MM-HH:MM'"
        
        start_time = parts[0].strip()
        end_time = parts[1].strip()
        
        # Normalize times (0 -> 00, 5 -> 05, etc.)
        start_normalized = normalize_time(start_time)
        end_normalized = normalize_time(end_time)
        
        # Validate that start <= end
        start_minutes = time_to_minutes(start_normalized)
        end_minutes = time_to_minutes(end_normalized)
        
        # Ensure start time is less than or equal to end time
        if start_minutes > end_minutes:
            return False, f"Start time must be less than or equal to end time: '{hour_range}' (start: {start_normalized}, end: {end_normalized})"
        
        # Update the list with normalized format
        hours_list[i] = f"{start_normalized}-{end_normalized}"
    
    return True, ""

def validate_rating(rating: float) -> tuple[bool, str]:
    """Validate rating is between 0.0 and 5.0"""
    if not isinstance(rating, (int, float)):
        return False, "Rating must be a number"
    if rating < 0.0 or rating > 5.0:
        return False, "Rating must be between 0.0 and 5.0"
    return True, ""

def validate_noise_level(noise_level: int) -> tuple[bool, str]:
    """Validate noise level is between 0 and 9"""
    if not isinstance(noise_level, int):
        return False, "Noise level must be an integer"
    if noise_level < 0 or noise_level > 9:
        return False, "Noise level must be between 0 and 9"
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

def cleanup_old_temporary_places(db: Session):
    """Delete temporary places (less than 5 ratings) that are older than 48 hours"""
    try:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=48)
        
        # Get all places with less than 5 ratings
        places = db.query(Place).all()
        deleted_count = 0
        
        for place in places:
            # Count ratings for this place
            ratings_count = db.query(func.count(Rating.id)).filter(
                Rating.place_id == place.id
            ).scalar()
            ratings_count = ratings_count or 0
            
            # Check if place is temporary and old enough
            if ratings_count < 5 and place.created_at:
                # Check if place is older than 48 hours
                if place.created_at < cutoff_time:
                    # Delete the place (cascade will delete ratings and tags)
                    db.delete(place)
                    deleted_count += 1
        
        if deleted_count > 0:
            db.commit()
            print(f"Cleaned up {deleted_count} old temporary places")
        
        return deleted_count
    except Exception as e:
        db.rollback()
        print(f"Error cleaning up temporary places: {e}")
        return 0

# Places API endpoints
@app.get("/api/places")
async def get_places(request: Request, db: Session = Depends(get_db)):
    """Get all places (available to all users)"""
    try:
        # Clean up old temporary places before returning list
        cleanup_old_temporary_places(db)
        # Try to get current user (optional)
        user = get_user_from_token(request, db)
        
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
            
            # Count number of ratings
            ratings_count = db.query(func.count(Rating.id)).filter(
                Rating.place_id == place.id
            ).scalar()
            ratings_count = ratings_count or 0
            
            # Check if place is temporary (less than 5 ratings)
            is_temporary = ratings_count < 5
            
            # Get user's rating if authenticated
            user_rating = None
            if user:
                user_rating_obj = db.query(Rating).filter(
                    Rating.place_id == place.id,
                    Rating.user_id == user.id
                ).first()
                if user_rating_obj:
                    user_rating = user_rating_obj.rating
            
            # Get tags from relationship
            tag_names = [tag.name for tag in place.tags]
            
            # Check if current user owns this place
            is_owner = user and place.user_id == user.id
            
            # Parse amenities safely
            try:
                amenities_list = json.loads(place.amenities) if place.amenities else []
                if not isinstance(amenities_list, list):
                    amenities_list = []
            except (json.JSONDecodeError, TypeError):
                amenities_list = []
            
            # Parse hours safely
            try:
                hours_list = json.loads(place.hours) if place.hours else []
                if not isinstance(hours_list, list):
                    hours_list = []
            except (json.JSONDecodeError, TypeError):
                hours_list = []
            
            places_data.append({
                "id": place.id,
                "latitude": place.latitude,
                "longitude": place.longitude,
                "name": place.name,
                "noise_level": place.noise_level,
                "amenities": amenities_list,
                "tags": tag_names,
                "rating": round(avg_rating, 1),
                "ratings_count": ratings_count,
                "is_temporary": is_temporary,
                "user_rating": user_rating,
                "hours": hours_list,
                "address": address or "",
                "is_owner": is_owner,
                "created_at": place.created_at.isoformat() if place.created_at else None
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

@app.put("/api/places/{place_id}")
async def update_place(
    place_id: int,
    request: Request,
    name: str = Form(...),
    noise_level: int = Form(1),
    amenities: str = Form("[]"),
    tags: str = Form("[]"),
    hours: str = Form("[]"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a place"""
    try:
        place = db.query(Place).filter(Place.id == place_id, Place.user_id == user.id).first()
        if not place:
            return JSONResponse(
                status_code=404,
                content={"detail": "Place not found"}
            )
        
        # Validate inputs
        is_valid, error_msg = validate_coordinates(place.latitude, place.longitude)
        if not is_valid:
            return JSONResponse(status_code=400, content={"detail": error_msg})
        
        is_valid, error_msg = validate_noise_level(noise_level)
        if not is_valid:
            return JSONResponse(status_code=400, content={"detail": error_msg})
        
        if not name or len(name.strip()) < 1:
            return JSONResponse(status_code=400, content={"detail": "Name is required"})
        
        # Parse and validate hours
        try:
            hours_list = json.loads(hours) if hours else []
            is_valid, error_msg = validate_hours_format(hours_list)
            if not is_valid:
                return JSONResponse(status_code=400, content={"detail": error_msg})
        except json.JSONDecodeError:
            return JSONResponse(status_code=400, content={"detail": "Invalid hours format"})
        
        # Parse and validate amenities
        try:
            amenities_list = json.loads(amenities) if amenities else []
            valid_amenities = {'wifi', 'outlets', 'bright'}
            if not all(a in valid_amenities for a in amenities_list):
                return JSONResponse(status_code=400, content={"detail": "Invalid amenities"})
        except json.JSONDecodeError:
            return JSONResponse(status_code=400, content={"detail": "Invalid amenities format"})
        
        # Parse and validate tags
        try:
            tags_list = json.loads(tags) if tags else []
            if not isinstance(tags_list, list):
                return JSONResponse(status_code=400, content={"detail": "Tags must be a list"})
        except json.JSONDecodeError:
            return JSONResponse(status_code=400, content={"detail": "Invalid tags format"})
        
        # Update place
        place.name = name.strip()
        place.noise_level = noise_level
        place.amenities = json.dumps(amenities_list)
        place.hours = json.dumps(hours_list)
        
        # Update tags
        place.tags.clear()
        for tag_name in tags_list:
            tag_name = tag_name.strip().lower()
            if tag_name:
                tag = db.query(Tag).filter(Tag.name == tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.add(tag)
                    db.flush()
                place.tags.append(tag)
        
        db.commit()
        return {"message": "Place updated successfully", "id": place.id}
    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error updating place: {str(e)}"}
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
