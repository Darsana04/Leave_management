import os
from database import engine, Base
import models  # noqa: F401 — registers models on Base
from logger import get_logger, LOG_FILE

Base.metadata.create_all(bind=engine)
print("✅ Tables created")

logger = get_logger()
logger.info("Application started")

print(logger.handlers)
print(os.path.abspath(LOG_FILE))