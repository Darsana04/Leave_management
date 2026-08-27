from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models import User, LeaveRequest, LeaveBalance, LeaveStatus
from schemas import LeaveRequestCreate, LeaveRequestOut, LeaveBalanceOut
from auth import get_current_user, require_manager
from services import apply_leave, approve_leave, reject_leave, get_balance_summary
from logger import logger

router = APIRouter(tags=["Leaves"])


# ---------------------------------------------------------
# POST /leaves — employee applies for leave
# ---------------------------------------------------------
@router.post("/leaves", response_model=LeaveRequestOut, status_code=status.HTTP_201_CREATED)
def apply_for_leave(
    data: LeaveRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        leave_request = apply_leave(
            db=db,
            employee=current_user,
            leave_type=data.leave_type,
            start_date=data.start_date,
            end_date=data.end_date,
            reason=data.reason,
        )
        return leave_request
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------
# GET /leaves/my — employee views their own leave requests
# ---------------------------------------------------------
@router.get("/leaves/my", response_model=List[LeaveRequestOut])
def my_leaves(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(LeaveRequest).filter(
        LeaveRequest.employee_id == current_user.id
    ).order_by(LeaveRequest.id.desc()).all()


# ---------------------------------------------------------
# GET /balance — employee views their own leave balance
# ---------------------------------------------------------
@router.get("/balance", response_model=LeaveBalanceOut)
def my_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    balance = db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == current_user.id
    ).first()
    if not balance:
        raise HTTPException(status_code=404, detail="Leave balance not found")

    return get_balance_summary(balance)


# ---------------------------------------------------------
# GET /manager/leaves/pending — manager views pending requests
# from their own team only
# ---------------------------------------------------------
@router.get("/manager/leaves/pending", response_model=List[LeaveRequestOut])
def pending_leaves(
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db),
):
    return (
        db.query(LeaveRequest)
        .join(User, LeaveRequest.employee_id == User.id)
        .filter(User.manager_id == current_user.id, LeaveRequest.status == LeaveStatus.PENDING)
        .all()
    )


# ---------------------------------------------------------
# PUT /manager/leaves/{id}/approve
# ---------------------------------------------------------
@router.put("/manager/leaves/{leave_id}/approve", response_model=LeaveRequestOut)
def approve(
    leave_id: int,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db),
):
    try:
        return approve_leave(db=db, leave_request_id=leave_id, approver=current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------
# PUT /manager/leaves/{id}/reject
# ---------------------------------------------------------
@router.put("/manager/leaves/{leave_id}/reject", response_model=LeaveRequestOut)
def reject(
    leave_id: int,
    current_user: User = Depends(require_manager),
    db: Session = Depends(get_db),
):
    try:
        return reject_leave(db=db, leave_request_id=leave_id, approver=current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))