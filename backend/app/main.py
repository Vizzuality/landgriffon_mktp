from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.routers.router import router
from app.database import engine, Base
import threading
from app.pubsub import subscribe_to_pubsub
import os
import logging
from app.logging_config import setup_logging
from backend.config import load_environment

load_environment()

setup_logging()

logger = logging.getLogger(__name__)

logger.info(f"Environment variables loaded: {os.getenv('ENVIRONMENT')}")
logger.info(f"GOOGLE_CLOUD_PROJECT: {os.getenv('GOOGLE_CLOUD_PROJECT')}")
logger.info(f"PUBSUB_SUBSCRIPTION: {os.getenv('PUBSUB_SUBSCRIPTION')}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup event
    logger.info("Starting Pub/Sub subscriber...")
    subscriber_thread = threading.Thread(target=subscribe_to_pubsub, daemon=True)
    subscriber_thread.start()
    
    yield
    
    # Shutdown event
    logger.info("Stopping Pub/Sub subscriber...")

app = FastAPI(lifespan=lifespan)

app.include_router(router)

# Create the database tables
Base.metadata.create_all(bind=engine)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Landgriffon Marketplace API"}
