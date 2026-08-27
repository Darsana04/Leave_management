import enum
from datetime import date
from typing import Optional
from sqlalchemy import String, ForeignKey, Enum as SqlEnum, Float, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class UserRole(enum.Enum):
    EMPLOYEE = "EMPLOYEE"
    MANAGER = "MANAGER"


class LeaveStatus(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class LeaveType(enum.Enum):
    CASUAL = "CASUAL"
    SICK = "SICK"
    EARNED = "EARNED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SqlEnum(UserRole), default=UserRole.EMPLOYEE)

    # --- Self-referential FK: an employee points to their manager (another User) ---
    manager_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # The manager THIS user reports to (one manager)
    manager: Mapped[Optional["User"]] = relationship(
        remote_side=[id],
        back_populates="team_members"
    )

    # The employees THIS user manages (if they are a manager) — reverse side
    team_members: Mapped[list["User"]] = relationship(
        back_populates="manager"
    )

    leave_requests: Mapped[list["LeaveRequest"]] = relationship(
        back_populates="employee",
        foreign_keys="LeaveRequest.employee_id"
    )

    leave_balance: Mapped[Optional["LeaveBalance"]] = relationship(
        back_populates="employee",
        uselist=False
    )


class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)

    # Casual
    casual_total: Mapped[float] = mapped_column(Float, default=12)
    casual_used: Mapped[float] = mapped_column(Float, default=0)

    # Sick
    sick_total: Mapped[float] = mapped_column(Float, default=10)
    sick_used: Mapped[float] = mapped_column(Float, default=0)

    # Earned
    earned_total: Mapped[float] = mapped_column(Float, default=15)
    earned_used: Mapped[float] = mapped_column(Float, default=0)

    # Loss of Pay — no "total" because there's no limit, it's just a running count
    # of unpaid days accumulated whenever a request exceeds the available balance.
    lop_used: Mapped[float] = mapped_column(Float, default=0)

    employee: Mapped["User"] = relationship(back_populates="leave_balance")

    # ---- helper to fetch remaining balance for ANY leave type dynamically ----
    def remaining(self, leave_type: "LeaveType") -> float:
        mapping = {
            LeaveType.CASUAL: (self.casual_total, self.casual_used),
            LeaveType.SICK: (self.sick_total, self.sick_used),
            LeaveType.EARNED: (self.earned_total, self.earned_used),
        }
        total, used = mapping[leave_type]
        return total - used

    # ---- deduct paid days from the correct bucket ----
    def deduct(self, leave_type: "LeaveType", days: float):
        if leave_type == LeaveType.CASUAL:
            self.casual_used += days
        elif leave_type == LeaveType.SICK:
            self.sick_used += days
        elif leave_type == LeaveType.EARNED:
            self.earned_used += days

    # ---- record LOP days separately ----
    def add_lop(self, days: float):
        self.lop_used += days


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    leave_type: Mapped[LeaveType] = mapped_column(SqlEnum(LeaveType), default=LeaveType.CASUAL)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    days: Mapped[float] = mapped_column(Float, nullable=False)
    lop_days: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[LeaveStatus] = mapped_column(SqlEnum(LeaveStatus), default=LeaveStatus.PENDING)

    approved_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    employee: Mapped["User"] = relationship(
        back_populates="leave_requests",
        foreign_keys=[employee_id]
    )