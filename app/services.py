from datetime import date
from sqlalchemy.orm import Session

from models import User, LeaveRequest, LeaveBalance, LeaveType, LeaveStatus
from logger import logger

# ---------------------------------------------------------
# Business rule constants
# ---------------------------------------------------------
MAX_CONSECUTIVE_DAYS = 15


def calculate_days(start_date: date, end_date: date) -> float:
    if end_date < start_date:
        raise ValueError("end_date cannot be before start_date")
    return (end_date - start_date).days + 1


def validate_leave_request(start_date: date, end_date: date) -> float:
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")

    days = calculate_days(start_date, end_date)

    if days > MAX_CONSECUTIVE_DAYS:
        raise ValueError(
            f"Cannot apply for more than {MAX_CONSECUTIVE_DAYS} consecutive days"
        )

    return days


def apply_leave(
    db: Session,
    employee: User,
    leave_type: LeaveType,
    start_date: date,
    end_date: date,
    reason: str = None,
) -> LeaveRequest:
    days = validate_leave_request(start_date, end_date)

    leave_request = LeaveRequest(
        employee_id=employee.id,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        days=days,
        lop_days=0,
        status=LeaveStatus.PENDING,
    )
    db.add(leave_request)
    db.commit()
    db.refresh(leave_request)

    logger.info(
        f"Leave applied: employee_id={employee.id}, type={leave_type.value}, days={days}"
    )
    return leave_request


def calculate_lop(requested_days: float, available_days: float) -> tuple[float, float]:
    paid_days = min(requested_days, available_days)
    paid_days = max(paid_days, 0)
    lop_days = requested_days - paid_days
    return paid_days, lop_days


def approve_leave(db: Session, leave_request_id: int, approver: User) -> LeaveRequest:
    leave_request = db.query(LeaveRequest).filter(LeaveRequest.id == leave_request_id).first()
    if leave_request is None:
        raise ValueError("Leave request not found")

    if leave_request.status != LeaveStatus.PENDING:
        raise ValueError(f"Leave request is already {leave_request.status.value}")

    employee = db.query(User).filter(User.id == leave_request.employee_id).first()
    if employee.manager_id != approver.id:
        raise ValueError("You can only approve leave requests from your own team")

    balance = db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == leave_request.employee_id
    ).first()
    if balance is None:
        raise ValueError("Leave balance record not found for this employee")

    available = balance.remaining(leave_request.leave_type)
    paid_days, lop_days = calculate_lop(leave_request.days, available)

    balance.deduct(leave_request.leave_type, paid_days)
    if lop_days > 0:
        balance.add_lop(lop_days)

    leave_request.lop_days = lop_days
    leave_request.status = LeaveStatus.APPROVED
    leave_request.approved_by = approver.id

    db.commit()
    db.refresh(leave_request)

    logger.info(
        f"Leave approved: request_id={leave_request.id}, employee_id={leave_request.employee_id}, "
        f"paid_days={paid_days}, lop_days={lop_days}, approved_by={approver.id}"
    )
    return leave_request


def reject_leave(db: Session, leave_request_id: int, approver: User) -> LeaveRequest:
    leave_request = db.query(LeaveRequest).filter(LeaveRequest.id == leave_request_id).first()
    if leave_request is None:
        raise ValueError("Leave request not found")

    if leave_request.status != LeaveStatus.PENDING:
        raise ValueError(f"Leave request is already {leave_request.status.value}")

    employee = db.query(User).filter(User.id == leave_request.employee_id).first()
    if employee.manager_id != approver.id:
        raise ValueError("You can only reject leave requests from your own team")

    leave_request.status = LeaveStatus.REJECTED
    leave_request.approved_by = approver.id

    db.commit()
    db.refresh(leave_request)

    logger.info(
        f"Leave rejected: request_id={leave_request.id}, employee_id={leave_request.employee_id}, "
        f"rejected_by={approver.id}"
    )
    return leave_request


def get_balance_summary(balance: LeaveBalance) -> dict:
    return {
        "casual_total": balance.casual_total,
        "casual_used": balance.casual_used,
        "sick_total": balance.sick_total,
        "sick_used": balance.sick_used,
        "earned_total": balance.earned_total,
        "earned_used": balance.earned_used,
        "lop_used": balance.lop_used,
        "casual_remaining": balance.remaining(LeaveType.CASUAL),
        "sick_remaining": balance.remaining(LeaveType.SICK),
        "earned_remaining": balance.remaining(LeaveType.EARNED),
    }