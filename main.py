from fastapi import FastAPI, Depends, Request, Form, HTTPException, status
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
from models import User, UserMap

app = FastAPI(title="QuiteMap", description="Interactive Maps with Authentication")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

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

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
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
        "user": user
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