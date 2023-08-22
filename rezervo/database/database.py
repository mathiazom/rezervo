from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from rezervo.settings import get_settings

engine = create_engine(get_settings().DATABASE_CONNECTION_STRING)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
