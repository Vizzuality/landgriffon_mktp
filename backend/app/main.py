from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.routers.router import router
from app.database import engine, Base
import threading
from app.pubsub import subscribe_to_pubsub
from dotenv import load_dotenv
import os
import logging
from app.logging_config import setup_logging

# Load environment variables from .env file
load_dotenv()

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

logger.info("Environment variables loaded:")
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
    # Perform any cleanup if necessary

app = FastAPI(lifespan=lifespan)

# Include the router for API endpoints
app.include_router(router)

# Create the database tables
Base.metadata.create_all(bind=engine)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Landgriffon Marketplace API"}
