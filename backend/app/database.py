import os
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.config import load_environment

load_environment()
SQLALCHEMY_DATABASE_URL = os.getenv('ACCOUNTS_DATABASE')

# Create async engine
engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True)

# Create async session factory
SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

# Dependency to get the session
async def get_db():
    async with SessionLocal() as session:
        yield session
