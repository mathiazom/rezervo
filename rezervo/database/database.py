from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from rezervo.schemas.config.config import read_app_config

engine = create_engine(read_app_config().database_connection_string)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
