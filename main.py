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
from datetime import datetime, timedelta
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import secrets
from config import settings
from models import User, UserMap, Place

app = FastAPI(title="QuiteMap", description="Interactive Maps with Authentication")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

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
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
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
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Register new user"""
    try:
        existing_user = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            return JSONResponse(
                status_code=400,
                content={"detail": "Username or email already registered"}
            )
        
        hashed_password = get_password_hash(password)
        user = User(
            username=username,
            email=email,
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
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
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
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            expires=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
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

# Protected API routes
@app.get("/api/maps")
async def get_user_maps(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get user's saved maps (protected)"""
    try:
        maps = db.query(UserMap).filter(UserMap.user_id == user.id).all()
        return {
            "message": f"Hello {user.username}!",
            "user_maps": [{"id": m.id, "name": m.map_name} for m in maps]
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error loading maps: {str(e)}"}
        )

@app.post("/api/maps")
async def save_map(
    map_name: str = Form(...),
    map_config: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save user's map configuration (protected)"""
    try:
        user_map = UserMap(
            user_id=user.id,
            map_name=map_name,
            map_config=map_config
        )
        db.add(user_map)
        db.commit()
        return {"message": "Map saved successfully", "map_id": user_map.id}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error saving map: {str(e)}"}
        )

@app.get("/public/maps")
async def get_public_maps(db: Session = Depends(get_db)):
    """Get public maps (no authentication required)"""
    try:
        public_maps = db.query(UserMap).filter(UserMap.is_public == True).all()
        return {"public_maps": [{"id": m.id, "name": m.map_name} for m in public_maps]}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error loading public maps: {str(e)}"}
        )

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
async def get_user_places(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get user's places"""
    try:
        places = db.query(Place).filter(Place.user_id == user.id).all()
        places_data = []
        for place in places:
            # Get address from geocoder if not cached
            address = place.address
            if not address:
                address = await reverse_geocode(place.latitude, place.longitude)
                if address:
                    place.address = address
                    db.commit()
            
            places_data.append({
                "id": place.id,
                "latitude": place.latitude,
                "longitude": place.longitude,
                "name": place.name,
                "type": place.type,
                "noise_level": place.noise_level,
                "amenities": json.loads(place.amenities) if place.amenities else [],
                "tags": json.loads(place.tags) if place.tags else [],
                "rating": place.rating,
                "hours": place.hours,
                "status": place.status,
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
    type: str = Form(...),
    noise_level: int = Form(1),
    amenities: str = Form("[]"),
    tags: str = Form("[]"),
    rating: float = Form(0.0),
    hours: str = Form(None),
    status: str = Form("open"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new place"""
    try:
        # Get address from geocoder
        address = await reverse_geocode(latitude, longitude)
        
        place = Place(
            user_id=user.id,
            latitude=latitude,
            longitude=longitude,
            name=name,
            type=type,
            noise_level=noise_level,
            amenities=amenities,
            tags=tags,
            rating=rating,
            hours=hours,
            status=status,
            address=address
        )
        db.add(place)
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
