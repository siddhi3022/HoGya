from datetime import datetime, timedelta, timezone
from typing import Optional, List
import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from .database import get_db
from . import models

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@12345"
ADMIN_ROLE = "admin"
INTERNAL_SERVICE_TOKEN = "microservices-internal-secret-token-2026"

JWT_SECRET_KEY = "microservices-shared-secret-key-at-least-32-bytes-long!"
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# HTTPBearer enables the Swagger UI "Authorize" dialog
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash a plain text password using bcrypt (handling 72-byte truncation safely)."""
    pwd_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    pwd_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))


def init_admin_user(db: Session):
    """
    Idempotent admin initialization.
    - If primary admin does not exist: create admin with ADMIN_USERNAME and ADMIN_PASSWORD.
    - If primary admin already exists: do not duplicate; ensure password and role match configuration.
    """
    admin_user = db.query(models.User).filter(models.User.username == ADMIN_USERNAME).first()
    if not admin_user:
        hashed_pwd = hash_password(ADMIN_PASSWORD)
        new_admin = models.User(
            username=ADMIN_USERNAME,
            hashed_password=hashed_pwd,
            role=ADMIN_ROLE
        )
        db.add(new_admin)
        db.commit()
        db.refresh(new_admin)
        print(f"[*] Bootstrap: Initialized primary admin '{ADMIN_USERNAME}' (role: {ADMIN_ROLE})")
    else:
        # Sync password and role with env configuration
        modified = False
        if not verify_password(ADMIN_PASSWORD, admin_user.hashed_password):
            admin_user.hashed_password = hash_password(ADMIN_PASSWORD)
            modified = True
        if admin_user.role != ADMIN_ROLE:
            admin_user.role = ADMIN_ROLE
            modified = True
        if modified:
            db.commit()
            print(f"[*] Bootstrap: Synchronized primary admin credentials for '{ADMIN_USERNAME}'")


def create_access_token(user_id: int, username: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token with user_id, username, role, and exp."""
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode = {
        "sub": str(user_id),
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": expire
    }
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> models.User:
    """Validate JWT token and return the current authenticated user."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Bearer token missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id_raw = payload.get("user_id") or payload.get("sub")
        username: Optional[str] = payload.get("username")
        role: str = payload.get("role", "customer")

        if not username and not user_id_raw:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload: claims missing",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not username:
            username = str(user_id_raw)
        user_id = int(user_id_raw) if str(user_id_raw).isdigit() else 0
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        return models.User(id=user_id, username=username, role=role)
    return user


def require_roles(allowed_roles: List[str]):
    """FastAPI dependency to enforce Role-Based Access Control (RBAC)."""
    def role_checker(current_user: models.User = Depends(get_current_user)) -> models.User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required role: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker
