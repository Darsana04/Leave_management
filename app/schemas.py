from datetime import date
from typing import Optional
from pydantic import BaseModel, ConfigDict
from models import UserRole, LeaveType, LeaveStatus


# ============================================================
# USER SCHEMAS
# ============================================================

class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    manager_id: Optional[int] = None
    # role intentionally excluded — server always assigns EMPLOYEE


class UserLogin(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: UserRole
    manager_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ============================================================
# LEAVE BALANCE SCHEMAS
# ============================================================

class LeaveBalanceOut(BaseModel):
    casual_total: float
    casual_used: float
    sick_total: float
    sick_used: float
    earned_total: float
    earned_used: float
    lop_used: float

    casual_remaining: float
    sick_remaining: float
    earned_remaining: float

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# LEAVE REQUEST SCHEMAS
# ============================================================

class LeaveRequestCreate(BaseModel):
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: Optional[str] = None


class LeaveRequestOut(BaseModel):
    id: int
    employee_id: int
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: Optional[str] = None
    days: float
    lop_days: float
    status: LeaveStatus
    approved_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

# LeaveDecision removed — approve/reject happens via URL path only, no body needed