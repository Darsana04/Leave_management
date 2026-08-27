from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, LeaveBalance
from app.schemas import UserCreate, UserLogin, UserOut, Token
from app.auth import hash_password, verify_password, create_access_token
from app.logger import logger

router = APIRouter(tags=["Users"])


# ---------------------------------------------------------
# POST /register — public. Always creates an EMPLOYEE
# (role is never accepted from the client — see schemas.py).
# Also creates their LeaveBalance row in the same flow.
# ---------------------------------------------------------
@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    if user_data.manager_id:
        manager = db.query(User).filter(
            User.id == user_data.manager_id, User.role == UserRole.MANAGER
        ).first()
        if not manager:
            raise HTTPException(status_code=400, detail="Invalid manager_id")

    new_user = User(
        name=user_data.name,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        role=UserRole.EMPLOYEE,
        manager_id=user_data.manager_id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Auto-create leave balance with default limits
    balance = LeaveBalance(
        employee_id=new_user.id,
        casual_total=12, casual_used=0,
        sick_total=10, sick_used=0,
        earned_total=15, earned_used=0,
        lop_used=0,
    )
    db.add(balance)
    db.commit()

    logger.info(f"New user registered: id={new_user.id}, email={new_user.email}")
    return new_user


# ---------------------------------------------------------
# POST /login — returns a JWT access token
# ---------------------------------------------------------
@router.post("/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()

    if not user or not verify_password(credentials.password, user.password_hash):
        logger.warning(f"Failed login attempt for email={credentials.email}")
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"user_id": str(user.id), "role": user.role.value})
    logger.info(f"User logged in: id={user.id}, email={user.email}")

    return Token(access_token=token)