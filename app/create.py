from database import engine, Base
import models  # noqa: F401 — registers models on Base

Base.metadata.create_all(bind=engine)
print("✅ Tables created")