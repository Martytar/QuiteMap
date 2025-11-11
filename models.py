"""
Database models using SQLAlchemy ORM.
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float, ForeignKey, UniqueConstraint, Table
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base

# Association table for many-to-many relationship between Place and Tag
place_tags = Table(
    'place_tags',
    Base.metadata,
    Column('place_id', Integer, ForeignKey('places.id', ondelete='CASCADE'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True)
)

# Database models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    ratings = relationship("Rating", back_populates="user")

class Place(Base):
    __tablename__ = "places"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    name = Column(String(200), nullable=False)
    noise_level = Column(Integer, default=1)  # 1-4
    amenities = Column(Text, nullable=True)  # JSON string: ["wifi", "outlets"]
    hours = Column(Text, nullable=True)  # JSON string: ["10-13", "13-18"] - array of time ranges
    address = Column(String(500), nullable=True)  # cached address from geocoder
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    ratings = relationship("Rating", back_populates="place", cascade="all, delete-orphan")
    tags = relationship("Tag", secondary=place_tags, back_populates="places")

class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    places = relationship("Place", secondary=place_tags, back_populates="tags")

class Rating(Base):
    __tablename__ = "ratings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    place_id = Column(Integer, ForeignKey("places.id"), nullable=False, index=True)
    rating = Column(Float, nullable=False)  # 0.0 to 5.0
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="ratings")
    place = relationship("Place", back_populates="ratings")
    
    # Ensure one rating per user per place
    __table_args__ = (
        UniqueConstraint('user_id', 'place_id', name='uq_user_place_rating'),
    )
