import json
import os
import pprint
import uuid
from datetime import datetime
from google.cloud import pubsub_v1
from googleapiclient.discovery import build
from app.database import SessionLocal
from app.models import Account, Subscription
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT')
PUBSUB_SUBSCRIPTION = os.getenv('PUBSUB_SUBSCRIPTION')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Initialize Google API client
service = build('cloudcommerceprocurement', 'v1', developerKey=GOOGLE_API_KEY)

def _generate_internal_account_id():
    """Generate a unique internal account ID"""
    return str(uuid.uuid4())

def approve_account(procurement_account_id):
    """Approves the account in the Procurement Service."""
    name = f'providers/DEMO-{PROJECT_ID}/accounts/{procurement_account_id}'
    request = service.providers().accounts().approve(
        name=name, body={'approvalName': 'signup'})
    request.execute()

def approve_entitlement(entitlement_id):
    """Approves the entitlement in the Procurement Service."""
    name = f'providers/DEMO-{PROJECT_ID}/entitlements/{entitlement_id}'
    request = service.providers().entitlements().approve(name=name, body={})
    request.execute()

def fetch_entitlement_details(entitlement_id):
    """Fetches the details of an entitlement."""
    name = f'providers/DEMO-{PROJECT_ID}/entitlements/{entitlement_id}'
    request = service.providers().entitlements().get(name=name)
    response = request.execute()
    return response

def handle_account_created(payload, db):
    account_details = payload.get('account', {})
    procurement_account_id = account_details.get('id')

    if not procurement_account_id:
        logger.error("No procurement account ID found in the message.")
        return

    internal_account_id = _generate_internal_account_id()

    db_account = db.query(Account).filter(Account.procurement_account_id == procurement_account_id).first()
    if not db_account:
        db_account = Account(
            procurement_account_id=procurement_account_id,
            internal_account_id=internal_account_id,
            status='pending'  # Assuming new accounts start in 'pending' status
        )
        db.add(db_account)
        db.commit()
        logger.info(f"Account created: {procurement_account_id}")
    else:
        logger.info(f"Account already exists: {procurement_account_id}")

def handle_entitlement_creation_requested(payload, db):
    entitlement = payload.get('entitlement', {})
    subscription_id = entitlement.get('id')
    if not subscription_id:
        logger.error("No subscription ID found in the message.")
        return

    # Fetch the entitlement details to get the associated account ID and plan details
    entitlement_details = fetch_entitlement_details(subscription_id)
    procurement_account_id = entitlement_details.get('account').split('/')[-1]
    product_id = entitlement_details.get('product')
    plan_id = entitlement_details.get('plan')
    consumer_id = entitlement_details.get('usageReportingId')
    start_time = entitlement_details.get('createTime')

    # Convert start_time to datetime object
    start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))

    db_account = db.query(Account).filter(Account.procurement_account_id == procurement_account_id).first()
    if db_account:
        db_subscription = db.query(Subscription).filter(Subscription.subscription_id == subscription_id).first()
        if not db_subscription:
            db_subscription = Subscription(
                account_id=db_account.id,
                subscription_id=subscription_id,
                product_id=product_id,
                plan_id=plan_id,
                consumer_id=consumer_id,
                start_time=start_time,
                status='pending'
            )
            db.add(db_subscription)
        else:
            db_subscription.product_id = product_id
            db_subscription.plan_id = plan_id
            db_subscription.consumer_id = consumer_id
            db_subscription.start_time = start_time
            db_subscription.status = "pending"
        db.commit()
        logger.info(f"Entitlement creation requested: {subscription_id}")
    else:
        # Store the entitlement with a reference to the account but don't approve it yet
        db_subscription = Subscription(
            subscription_id=subscription_id,
            product_id=product_id,
            plan_id=plan_id,
            consumer_id=consumer_id,
            start_time=start_time,
            status='pending'
        )
        db.add(db_subscription)
        db.commit()
        logger.info(f"Entitlement stored for later approval: {subscription_id}")

def handle_entitlement_active(payload, db):
    entitlement = payload.get('entitlement', {})
    subscription_id = entitlement.get('id')
    if not subscription_id:
        logger.error("No subscription ID found in the message.")
        return

    db_subscription = db.query(Subscription).filter(Subscription.subscription_id == subscription_id).first()
    if db_subscription:
        db_subscription.status = "active"
        db.commit()
        logger.info(f"Entitlement activated: {subscription_id}")
        # Set up resources for the customer here
    else:
        logger.error(f"No subscription found for ID {subscription_id} to activate.")

def handle_entitlement_cancelled(payload, db):
    entitlement = payload.get('entitlement', {})
    subscription_id = entitlement.get('id')
    if not subscription_id:
        logger.error("No subscription ID found in the message.")
        return

    db_subscription = db.query(Subscription).filter(Subscription.subscription_id == subscription_id).first()
    if db_subscription:
        db_subscription.status = "canceled"
        db.commit()
        logger.info(f"Entitlement canceled: {subscription_id}")
    else:
        logger.error(f"No subscription found for ID {subscription_id} to cancel.")

def handle_account_approved(procurement_account_id, db):
    """Handles account approval and related entitlement approvals."""
    db_account = db.query(Account).filter(Account.procurement_account_id == procurement_account_id).first()
    if db_account and db_account.status == 'active':
        # Approve all pending entitlements for this account
        pending_entitlements = db.query(Subscription).filter(Subscription.account_id == db_account.id, Subscription.status == 'pending').all()
        for entitlement in pending_entitlements:
            try:
                approve_entitlement(entitlement.subscription_id)
                entitlement.status = 'active'
                db.commit()
                logger.info(f"Entitlement approved: {entitlement.subscription_id}")
            except Exception as e:
                logger.error(f"Failed to approve entitlement {entitlement.subscription_id}: {e}")
    else:
        logger.error(f"No active account found for ID {procurement_account_id} to approve entitlements.")

def callback(message):
    payload = json.loads(message.data)
    logger.info(f"Received message: {payload}")
    
    event_type = payload.get("eventType", "")
    db = SessionLocal()
    
    try:
        event_handlers = {
            "ACCOUNT_ACTIVE": handle_account_created,
            "ENTITLEMENT_CREATION_REQUESTED": handle_entitlement_creation_requested,
            "ENTITLEMENT_ACTIVE": handle_entitlement_active,
            "ENTITLEMENT_CANCELLED": handle_entitlement_cancelled,
        }

        handler = event_handlers.get(event_type)
        if handler:
            handler(payload, db)
        else:
            logger.error(f"Unknown event type for message: {payload}")
    except Exception as e:
        logger.error(f"Error processing message: {e}")
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
