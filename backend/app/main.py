import os
import logging
import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.routers.router import router
from app.database import engine, Base
from app.pubsub import subscribe_to_pubsub
from app.logging_config import setup_logging
from app.config import load_environment

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
    pubsub_task = asyncio.create_task(subscribe_to_pubsub())
    
    # Create the database tables asynchronously
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    # Shutdown event
    logger.info("Stopping Pub/Sub subscriber...")
    pubsub_task.cancel()
    try:
        await pubsub_task
    except asyncio.CancelledError:
        logger.info("Pub/Sub subscriber cancelled")

app = FastAPI(lifespan=lifespan)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, log_level="info")
