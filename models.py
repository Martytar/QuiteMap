"""
Database models using SQLAlchemy ORM.
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float
from sqlalchemy.sql import func
from database import Base

class Post(Base):
    """
    Example Post model.
    
    Demonstrates relationships and text fields.
    """
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    content = Column(Text, nullable=False)
    author_id = Column(Integer, nullable=False, index=True)  # Foreign key to users
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Post(id={self.id}, title='{self.title}', author_id={self.author_id})>"

# Database models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Place(Base):
    __tablename__ = "places"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    name = Column(String(200), nullable=False)
    type = Column(String(50), nullable=False)  # cafe, library, coworking
    noise_level = Column(Integer, default=1)  # 1-4
    amenities = Column(Text, nullable=True)  # JSON string: ["wifi", "outlets"]
    tags = Column(Text, nullable=True)  # JSON string: ["tag1", "tag2"]
    rating = Column(Float, default=0.0)
    hours = Column(String(50), nullable=True)  # "08:00-22:00" or "24/7"
    status = Column(String(20), default="open")  # open, closed
    address = Column(String(500), nullable=True)  # cached address from geocoder
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
