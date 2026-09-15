from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas, auth

router = APIRouter(prefix="/auth")


# ----------------------------------------------------
# Authentication Endpoints
# ----------------------------------------------------
@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED, tags=["Authentication"])
def register(user_in: schemas.UserRegister, db: Session = Depends(get_db)):
    """
    Public user registration.
    - Accepts strictly {"username": "...", "password": "..."}.
    - Every normally registered user automatically receives role = 'customer'.
    - Any submitted role field is ignored.
    - Rejects duplicate usernames with HTTP 400 without modifying existing accounts.
    """
    existing_user = db.query(models.User).filter(models.User.username == user_in.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    hashed_pwd = auth.hash_password(user_in.password)
    new_user = models.User(
        username=user_in.username,
        hashed_password=hashed_pwd,
        role="customer"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/login", response_model=schemas.TokenResponse, tags=["Authentication"])
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and issue a JWT containing sub, user_id, username, and role."""
    user = db.query(models.User).filter(models.User.username == credentials.username).first()
    if not user or not auth.verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = auth.create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=schemas.UserResponse, tags=["Authentication"])
def get_me(current_user: models.User = Depends(auth.get_current_user)):
    """Get profile of the currently authenticated user."""
    return current_user


# ----------------------------------------------------
# Admin User Management Endpoints
# ----------------------------------------------------
@router.get("/users", response_model=List[schemas.UserResponse], tags=["Admin User Management"])
def get_all_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles(["admin"]))
):
    """
    List all registered users in the service.
    Restricted to ADMIN role only.
    Returns only safe fields (id, username, role); never passwords or tokens.
    """
    return db.query(models.User).all()


@router.delete("/users/{user_id}", status_code=status.HTTP_200_OK, tags=["Admin User Management"])
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles(["admin"]))
):
    """
    Delete a registered user account.
    Restricted to ADMIN role only.
    The primary admin account is protected and cannot be deleted.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )

    # Protect the primary admin account
    if user.username == auth.ADMIN_USERNAME or (user.role == "admin" and user.id == 1):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The primary admin account cannot be deleted"
        )

    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}
