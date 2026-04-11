"""
=============================================================
  File : backend/app/models/camera_model.py
  Purpose : Camera ORM model
=============================================================
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.db.database import Base


class Camera(Base):
    __tablename__ = "cameras"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String,  nullable=False)
    source     = Column(String,  nullable=False)   # "0" or "http://..."
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())