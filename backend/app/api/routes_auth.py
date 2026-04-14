"""
=============================================================
  File : backend/app/api/routes_auth.py
  Purpose : Auth endpoints — register, login, profile
=============================================================
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user_model import User
from app.core.security import (
    hash_password, verify_password,
    create_access_token, get_current_user,
)
from app.schemas.schemas import RegisterRequest, TokenResponse, UserOut

router = APIRouter()


@router.post("/register", response_model=UserOut, status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Create a new user account."""
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(400, "Username already taken")
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(400, "Email already registered")

    user = User(
        username  = req.username,
        email     = req.email,
        hashed_pw = hash_password(req.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(
    form_data : OAuth2PasswordRequestForm = Depends(),
    db        : Session = Depends(get_db),
):
    """
    Login with OAuth2 form-data (username + password fields).
    Frontend sends: Content-Type: application/x-www-form-urlencoded
    Returns JWT access token.
    """
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_pw):
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail      = "Incorrect username or password",
        )
    if not user.is_active:
        raise HTTPException(403, "Account disabled")

    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
def me(
    current_user : dict    = Depends(get_current_user),
    db           : Session = Depends(get_db),
):
    """Get current logged-in user's profile."""
    user = db.query(User).filter(
        User.username == current_user["username"]
    ).first()
    if not user:
        raise HTTPException(404, "User not found")
    return user