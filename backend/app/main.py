from fastapi import FastAPI
from app.routers.router import router
from app.database import engine, Base
from app.pubsub import subscribe_to_pubsub, stop_subscriber
import os
import logging
from app.logging_config import setup_logging
from app.config import load_environment
import threading

load_environment()

setup_logging()

logger = logging.getLogger(__name__)

logger.info(f"Environment variables loaded: {os.getenv('ENVIRONMENT')}")
logger.info(f"GOOGLE_CLOUD_PROJECT: {os.getenv('GOOGLE_CLOUD_PROJECT')}")
logger.info(f"PUBSUB_SUBSCRIPTION: {os.getenv('PUBSUB_SUBSCRIPTION')}")

def create_database():
    Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.on_event("startup")
def on_startup():
    logger.info("Starting Pub/Sub subscriber...")
    threading.Thread(target=subscribe_to_pubsub, daemon=True).start()  # Start the subscriber in a daemon thread
    create_database()

@app.on_event("shutdown")
def on_shutdown():
    logger.info("Stopping Pub/Sub subscriber...")
    stop_subscriber()

app.include_router(router)

