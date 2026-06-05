# db.py

import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

raw_database_url = os.environ.get("DATABASE_URL", "sqlite:///instance/facesinq.db")
if raw_database_url.startswith("postgres://"):
    raw_database_url = raw_database_url.replace("postgres://", "postgresql://", 1)
    logger.info("Using PostgreSQL database")

engine = create_engine(raw_database_url)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def initialize_database():
    logger.info("Initializing the database...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully.")
