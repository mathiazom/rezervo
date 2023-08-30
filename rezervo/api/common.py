from fastapi.security import HTTPBearer

from rezervo.database.database import SessionLocal


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Scheme for the Authorization header
token_auth_scheme = HTTPBearer()
