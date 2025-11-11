from fastapi import Depends, FastAPI, HTTPException
from fastapi_users import FastAPIUsers, models
from fastapi_users.authentication import JWTAuthentication
from fastapi_users.db import SQLAlchemyBaseUserTable, SQLAlchemyUserDatabase
from sqlalchemy import Column, String, Boolean, Integer
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./users.db"
SECRET = "your-secret-key-here" 

Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class UserTable(Base, SQLAlchemyBaseUserTable):
    pass

Base.metadata.create_all(bind=engine)

class User(models.BaseUser):
    pass

class UserCreate(models.BaseUserCreate):
    pass

class UserUpdate(models.BaseUserUpdate):
    pass

class UserDB(User, models.BaseUserDB):
    pass

def get_user_db():
    session = SessionLocal()
    try:
        yield SQLAlchemyUserDatabase(UserDB, session, UserTable)
    finally:
        session.close()

def get_jwt_strategy():
    return JWTAuthentication(secret=SECRET, lifetime_seconds=3600)

fastapi_users = FastAPIUsers(
    get_user_db,
    get_jwt_strategy,
    User,
    UserCreate,
    UserUpdate,
    UserDB,
)

current_active_user = fastapi_users.current_user(active=True)