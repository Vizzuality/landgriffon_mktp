import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import load_environment

load_environment()

# Get the database URL from the environment variable
SQLALCHEMY_DATABASE_URL = os.getenv("ACCOUNTS_DATABASE", "postgresql+psycopg2://user:password@localhost/dbname")

# Determine the connect arguments based on the database being used
connect_args = {}

# Create the database engine
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Function to get a new database session
def get_db():
    db = SessionLocal()
    try:
        yield db  # This is a synchronous generator function
    finally:
        db.close()
