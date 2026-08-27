import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserRole
from logger import logger

# ---------------------------------------------------------
# Config — pulled from .env (never hardcode secrets)
# ---------------------------------------------------------
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-fallback-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8   # 8 hours — fine for a demo/assessment

# ---------------------------------------------------------
# Password hashing
# ---------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------
# JWT creation
# ---------------------------------------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ---------------------------------------------------------
# Tell FastAPI where clients get their token from (used for
# Swagger UI's "Authorize" button + extracting the Bearer token)
# ---------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# ---------------------------------------------------------
# Decode token + fetch the current user — used as a dependency
# on every protected route.
# ---------------------------------------------------------
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        logger.warning("JWT decode failed — invalid or expired token")
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception

    return user


# ---------------------------------------------------------
# Authorization — restrict a route to managers only
# ---------------------------------------------------------
def require_manager(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.MANAGER:
        logger.warning(
            f"Unauthorized manager-action attempt by user_id={current_user.id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires manager privileges",
        )
    return current_user