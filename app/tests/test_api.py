"""
Full API integration tests — Arrange / Act / Assert style.
Bare imports — run from inside app/.
Uses an isolated SQLite test DB so real Postgres data is never touched.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from database import Base, get_db
from models import User, UserRole
from auth import hash_password

# ---------------------------------------------------------
# Isolated test database
# ---------------------------------------------------------
TEST_DATABASE_URL = "sqlite:///./test_leave.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def seeded_manager():
    db = TestingSessionLocal()
    manager = User(
        name="Test Manager",
        email="manager@test.com",
        password_hash=hash_password("managerpass"),
        role=UserRole.MANAGER,
    )
    db.add(manager)
    db.commit()
    db.refresh(manager)
    manager_id = manager.id
    db.close()
    return manager_id


def _register_and_login(email, password, manager_id):
    client.post("/register", json={
        "name": "Test Employee", "email": email, "password": password, "manager_id": manager_id
    })
    token = client.post("/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _manager_headers():
    token = client.post("/login", json={"email": "manager@test.com", "password": "managerpass"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ============================================================
# REGISTRATION
# ============================================================

def test_register_employee_success(seeded_manager):
    payload = {"name": "Arjun", "email": "arjun@test.com", "password": "arjun1234", "manager_id": seeded_manager}
    response = client.post("/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "arjun@test.com"
    assert data["role"] == "EMPLOYEE"
    assert "password" not in data
    assert "password_hash" not in data


def test_register_duplicate_email_fails(seeded_manager):
    payload = {"name": "Arjun", "email": "dup@test.com", "password": "pass1234", "manager_id": seeded_manager}
    client.post("/register", json=payload)
    response = client.post("/register", json=payload)
    assert response.status_code == 400


def test_register_invalid_manager_id_fails(seeded_manager):
    payload = {"name": "Arjun", "email": "badmgr@test.com", "password": "pass1234", "manager_id": 9999}
    response = client.post("/register", json=payload)
    assert response.status_code == 400


def test_register_cannot_self_assign_manager_role(seeded_manager):
    payload = {
        "name": "Sneaky", "email": "sneaky@test.com", "password": "pass1234",
        "manager_id": seeded_manager, "role": "MANAGER"
    }
    response = client.post("/register", json=payload)
    assert response.status_code == 201
    assert response.json()["role"] == "EMPLOYEE"


# ============================================================
# LOGIN
# ============================================================

def test_login_success(seeded_manager):
    client.post("/register", json={"name": "A", "email": "login@test.com", "password": "mypassword", "manager_id": seeded_manager})
    response = client.post("/login", json={"email": "login@test.com", "password": "mypassword"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password_fails(seeded_manager):
    client.post("/register", json={"name": "A", "email": "wrongpass@test.com", "password": "correctpass", "manager_id": seeded_manager})
    response = client.post("/login", json={"email": "wrongpass@test.com", "password": "wrongpass"})
    assert response.status_code == 401


def test_login_nonexistent_user_fails():
    response = client.post("/login", json={"email": "ghost@test.com", "password": "whatever"})
    assert response.status_code == 401


# ============================================================
# APPLY LEAVE
# ============================================================

def test_apply_leave_success(seeded_manager):
    headers = _register_and_login("apply@test.com", "pass1234", seeded_manager)
    response = client.post("/leaves", headers=headers, json={
        "leave_type": "CASUAL", "start_date": "2026-09-01", "end_date": "2026-09-03", "reason": "Family event"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "PENDING"
    assert data["days"] == 3
    assert data["lop_days"] == 0


def test_apply_leave_exceeding_max_days_fails(seeded_manager):
    headers = _register_and_login("toolong@test.com", "pass1234", seeded_manager)
    response = client.post("/leaves", headers=headers, json={
        "leave_type": "EARNED", "start_date": "2026-09-01", "end_date": "2026-09-20"
    })
    assert response.status_code == 400


def test_apply_leave_end_before_start_fails(seeded_manager):
    headers = _register_and_login("baddate@test.com", "pass1234", seeded_manager)
    response = client.post("/leaves", headers=headers, json={
        "leave_type": "CASUAL", "start_date": "2026-09-10", "end_date": "2026-09-01"
    })
    assert response.status_code == 400


def test_apply_leave_without_auth_fails():
    response = client.post("/leaves", json={
        "leave_type": "CASUAL", "start_date": "2026-09-01", "end_date": "2026-09-02"
    })
    assert response.status_code in (401, 403)


# ============================================================
# BALANCE
# ============================================================

def test_initial_balance_defaults(seeded_manager):
    headers = _register_and_login("balance@test.com", "pass1234", seeded_manager)
    response = client.get("/balance", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["casual_remaining"] == 12
    assert data["sick_remaining"] == 10
    assert data["earned_remaining"] == 15
    assert data["lop_used"] == 0


def test_balance_unchanged_while_pending(seeded_manager):
    headers = _register_and_login("pendingbal@test.com", "pass1234", seeded_manager)
    client.post("/leaves", headers=headers, json={
        "leave_type": "CASUAL", "start_date": "2026-09-01", "end_date": "2026-09-05"
    })
    response = client.get("/balance", headers=headers)
    assert response.json()["casual_used"] == 0


# ============================================================
# APPROVE — INCLUDING LOP
# ============================================================

def test_approve_leave_within_balance_no_lop(seeded_manager):
    emp_headers = _register_and_login("noLop@test.com", "pass1234", seeded_manager)
    leave_id = client.post("/leaves", headers=emp_headers, json={
        "leave_type": "CASUAL", "start_date": "2026-09-01", "end_date": "2026-09-03"
    }).json()["id"]

    mgr_headers = _manager_headers()
    response = client.put(f"/manager/leaves/{leave_id}/approve", headers=mgr_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "APPROVED"
    assert data["lop_days"] == 0

    balance = client.get("/balance", headers=emp_headers).json()
    assert balance["casual_used"] == 3
    assert balance["casual_remaining"] == 9


def test_approve_leave_creates_lop_when_over_balance(seeded_manager):
    emp_headers = _register_and_login("lop@test.com", "pass1234", seeded_manager)
    leave_id = client.post("/leaves", headers=emp_headers, json={
        "leave_type": "CASUAL", "start_date": "2026-09-01", "end_date": "2026-09-15"
    }).json()["id"]

    mgr_headers = _manager_headers()
    response = client.put(f"/manager/leaves/{leave_id}/approve", headers=mgr_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "APPROVED"
    assert data["lop_days"] == 3

    balance = client.get("/balance", headers=emp_headers).json()
    assert balance["casual_used"] == 12
    assert balance["casual_remaining"] == 0
    assert balance["lop_used"] == 3


def test_approve_already_processed_leave_fails(seeded_manager):
    emp_headers = _register_and_login("double@test.com", "pass1234", seeded_manager)
    leave_id = client.post("/leaves", headers=emp_headers, json={
        "leave_type": "CASUAL", "start_date": "2026-09-01", "end_date": "2026-09-02"
    }).json()["id"]

    mgr_headers = _manager_headers()
    client.put(f"/manager/leaves/{leave_id}/approve", headers=mgr_headers)

    response = client.put(f"/manager/leaves/{leave_id}/approve", headers=mgr_headers)
    assert response.status_code == 400


# ============================================================
# REJECT
# ============================================================

def test_reject_leave_does_not_change_balance(seeded_manager):
    emp_headers = _register_and_login("reject@test.com", "pass1234", seeded_manager)
    leave_id = client.post("/leaves", headers=emp_headers, json={
        "leave_type": "SICK", "start_date": "2026-09-01", "end_date": "2026-09-02"
    }).json()["id"]

    mgr_headers = _manager_headers()
    response = client.put(f"/manager/leaves/{leave_id}/reject", headers=mgr_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"

    balance = client.get("/balance", headers=emp_headers).json()
    assert balance["sick_used"] == 0
    assert balance["sick_remaining"] == 10


# ============================================================
# AUTHORIZATION / SECURITY
# ============================================================

def test_employee_cannot_approve_own_leave(seeded_manager):
    emp_headers = _register_and_login("selfapprove@test.com", "pass1234", seeded_manager)
    leave_id = client.post("/leaves", headers=emp_headers, json={
        "leave_type": "CASUAL", "start_date": "2026-09-01", "end_date": "2026-09-02"
    }).json()["id"]

    response = client.put(f"/manager/leaves/{leave_id}/approve", headers=emp_headers)
    assert response.status_code == 403


def test_employee_cannot_view_pending_list(seeded_manager):
    emp_headers = _register_and_login("nomgr@test.com", "pass1234", seeded_manager)
    response = client.get("/manager/leaves/pending", headers=emp_headers)
    assert response.status_code == 403


def test_manager_cannot_approve_other_managers_employee(seeded_manager):
    db = TestingSessionLocal()
    other_manager = User(
        name="Other Manager", email="othermgr@test.com",
        password_hash=hash_password("otherpass"), role=UserRole.MANAGER,
    )
    db.add(other_manager)
    db.commit()
    db.close()

    emp_headers = _register_and_login("teamtest@test.com", "pass1234", seeded_manager)
    leave_id = client.post("/leaves", headers=emp_headers, json={
        "leave_type": "CASUAL", "start_date": "2026-09-01", "end_date": "2026-09-02"
    }).json()["id"]

    other_mgr_token = client.post("/login", json={"email": "othermgr@test.com", "password": "otherpass"}).json()["access_token"]
    other_mgr_headers = {"Authorization": f"Bearer {other_mgr_token}"}

    response = client.put(f"/manager/leaves/{leave_id}/approve", headers=other_mgr_headers)
    assert response.status_code == 400


def test_manager_pending_list_only_shows_own_team(seeded_manager):
    emp_headers = _register_and_login("myteam@test.com", "pass1234", seeded_manager)
    client.post("/leaves", headers=emp_headers, json={
        "leave_type": "CASUAL", "start_date": "2026-09-01", "end_date": "2026-09-02"
    })

    mgr_headers = _manager_headers()
    response = client.get("/manager/leaves/pending", headers=mgr_headers)

    assert response.status_code == 200
    assert len(response.json()) == 1