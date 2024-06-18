import json
import os
from google.cloud import pubsub_v1
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

def handle_create_entitlement(payload, db_subscription):
    db_subscription.data = payload
    db_subscription.status = "pending"

def handle_cancel_entitlement(payload, db_subscription):
    if db_subscription:
        db_subscription.data = payload
        db_subscription.status = "canceled"
    else:
        logger.error(f"No subscription found for ID {payload.get('entitlement', {}).get('id')} to cancel.")

def handle_entitlement_plan_changed(payload, db_subscription):
    db_subscription.data = payload
    db_subscription.status = "pending update"

def handle_unknown_event(payload, db_subscription):
    logger.error(f"Unknown event type for message: {payload}")

event_handlers = {
    "CREATE_ENTITLEMENT": handle_create_entitlement,
    "CANCEL_ENTITLEMENT": handle_cancel_entitlement,
    "ENTITLEMENT_PLAN_CHANGED": handle_entitlement_plan_changed
}

def determine_event_handler(event_id):
    for prefix, handler in event_handlers.items():
        if event_id.startswith(prefix):
            return handler
    return handle_unknown_event

def callback(message):
    payload = json.loads(message.data)
    logger.info(f"Received message: {payload}")
    
    event_id = payload.get("eventId", "")
    entitlement = payload.get("entitlement", {})
    subscription_id = entitlement.get("id")
    
    if not subscription_id:
        logger.error("No subscription ID found in the message.")
        message.ack()
        return

    db = SessionLocal()
    try:
        db_subscription = db.query(Subscription).filter(Subscription.subscription_id == subscription_id).first()
        if not db_subscription and not event_id.startswith("CANCEL_ENTITLEMENT"):
            db_subscription = Subscription(subscription_id=subscription_id, data=payload)
            db.add(db_subscription)
        
        event_handler = determine_event_handler(event_id)
        event_handler(payload, db_subscription)

        db.commit()
        logger.info(f"Message with ID {subscription_id} processed and stored in database.")
    except Exception as e:
        logger.error(f"Error processing message with ID {subscription_id}: {e}")
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
