"""
One-time seed script — creates the first MANAGER account so employees
have a manager_id to register under.

Run this ONCE, after create_tables.py, before registering any employees:
    python seed.py

Safe to re-run? No — will fail with a duplicate email error if the
manager already exists. That's intentional (prevents accidental duplicates).
"""

from database import SessionLocal
from models import User, UserRole
from auth import hash_password
from logger import logger

db = SessionLocal()

try:
    existing = db.query(User).filter(User.email == "manager1@company.com").first()
    if existing:
        print(f"⚠️ Manager already exists: id={existing.id}, email={existing.email}")
    else:
        manager = User(
            name="Default Manager",
            email="manager1@company.com",
            password_hash=hash_password("manager1234"),   # change after first login, if you add that flow
            role=UserRole.MANAGER,
            manager_id=None,   # a manager has no manager above them in this simple model
        )
        db.add(manager)
        db.commit()
        db.refresh(manager)

        print(f"✅ Manager created: id={manager.id}, email={manager.email}")
        print(f"   Use manager_id={manager.id} when registering employees.")
        logger.info(f"Seed: manager created id={manager.id}")

except Exception as e:
    db.rollback()
    print("❌ Seeding failed:", e)

finally:
    db.close()