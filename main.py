from fastapi import FastAPI

from app.database import engine, Base
from app import models  # noqa: F401 — ensures models are registered before create_all
from app.routes import users, leaves
from app.logger import logger

# ---------------------------------------------------------
# Create tables on startup (fine for this project — no Alembic).
# In production you'd run migrations separately instead.
# ---------------------------------------------------------
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Leave Management System",
    description="A small backend REST API for managing employee leave, balances, and LOP.",
    version="1.0.0",
)

# ---------------------------------------------------------
# Register routers
# ---------------------------------------------------------
app.include_router(users.router)
app.include_router(leaves.router)


@app.on_event("startup")
def on_startup():
    logger.info(" Leave Management API starting up")


@app.get("/")
def root():
    return {"message": "Leave Management System API is running. Visit /docs for Swagger UI."}