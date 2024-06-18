import json
import os
from google.cloud import pubsub_v1
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.models import Subscription
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT')
PUBSUB_SUBSCRIPTION = os.getenv('PUBSUB_SUBSCRIPTION')

# Debugging statements to verify environment variables
logger.info(f"GOOGLE_CLOUD_PROJECT: {PROJECT_ID}")
logger.info(f"PUBSUB_SUBSCRIPTION: {PUBSUB_SUBSCRIPTION}")

def callback(message):
    payload = json.loads(message.data)
    logger.info(f"Received message: {payload}")
    
    subscription_id = payload.get('entitlement', {}).get('id')
    if subscription_id:
        db = SessionLocal()
        try:
            db_subscription = db.query(Subscription).filter(Subscription.subscription_id == subscription_id).first()
            if db_subscription:
                db_subscription.data = payload
                logger.info(f"Updating existing subscription with ID {subscription_id}")
            else:
                db_subscription = Subscription(subscription_id=subscription_id, data=payload)
                db.add(db_subscription)
                logger.info(f"Adding new subscription with ID {subscription_id}")
            db.commit()
            logger.info(f"Message with ID {subscription_id} stored in database.")
        except Exception as e:
            logger.error(f"Failed to store message in database: {e}")
        finally:
            db.close()
    
    message.ack()

def subscribe_to_pubsub():
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(PROJECT_ID, PUBSUB_SUBSCRIPTION)

    # Debugging statement to verify the subscription path
    logger.info(f'Subscription path: {subscription_path}')
    
    def wrapped_callback(message):
        callback(message)

    subscription = subscriber.subscribe(subscription_path, callback=wrapped_callback)
    logger.info(f'Listening for messages on {subscription_path}')
    try:
        subscription.result()
    except Exception as e:
        logger.error(f'Listening for messages on {subscription_path} threw an Exception: {e}')
