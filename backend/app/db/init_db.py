"""
=============================================================
  File : backend/app/db/init_db.py
  Purpose : Create all tables on startup
=============================================================
"""

from app.db.database import Base, engine
from app.models import user_model, camera_model   # import so Base sees them


def init_db():
    Base.metadata.create_all(bind=engine)