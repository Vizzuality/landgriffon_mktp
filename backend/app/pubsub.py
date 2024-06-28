from datetime import datetime
import json
import os
import asyncio
import uuid
from google.cloud import pubsub_v1
from googleapiclient.discovery import build
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from app.models import Account, Subscription
from app.config import load_environment
import logging

load_environment()

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT')
PUBSUB_SUBSCRIPTION = os.getenv('PUBSUB_SUBSCRIPTION')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Debugging statement to verify environment variables
ACCOUNTS_DATABASE = os.getenv('ACCOUNTS_DATABASE')
if ACCOUNTS_DATABASE is None:
    logger.error("ACCOUNTS_DATABASE is not set")
else:
    logger.info(f"ACCOUNTS_DATABASE: {ACCOUNTS_DATABASE}")

# Initialize the database connection
engine = create_async_engine(ACCOUNTS_DATABASE, echo=True, future=True)
AsyncSessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession
)

# Initialize Google API client
service = build('cloudcommerceprocurement', 'v1', developerKey=GOOGLE_API_KEY)

def _generate_internal_account_id():
    """Generate a unique internal account ID"""
    return str(uuid.uuid4())

async def approve_account(procurement_account_id):
    """Approves the account in the Procurement Service."""
    name = f'providers/{PROJECT_ID}/accounts/{procurement_account_id}'
    request = service.providers().accounts().approve(
        name=name, body={'approvalName': 'signup'})
    request.execute()

async def approve_entitlement(entitlement_id):
    """Approves the entitlement in the Procurement Service."""
    name = f'providers/{PROJECT_ID}/entitlements/{entitlement_id}'
    request = service.providers().entitlements().approve(name=name, body={})
    request.execute()

async def fetch_entitlement_details(entitlement_id):
    """Fetches the details of an entitlement."""
    name = f'providers/{PROJECT_ID}/entitlements/{entitlement_id}'
    request = service.providers().entitlements().get(name=name)
    response = request.execute()
    return response

async def handle_account_created(payload, session: AsyncSession):
    account_details = payload.get('account', {})
    procurement_account_id = account_details.get('id')

    if not procurement_account_id:
        logger.error("No procurement account ID found in the message.")
        return

    internal_account_id = _generate_internal_account_id()

    async with session.begin():
        result = await session.execute(select(Account).filter(Account.procurement_account_id == procurement_account_id))
        db_account = result.scalars().first()
        if not db_account:
            db_account = Account(
                procurement_account_id=procurement_account_id,
                internal_account_id=internal_account_id,
                status='pending'  # Assuming new accounts start in 'pending' status
            )
            session.add(db_account)
            await session.commit()
            logger.info(f"Account created: {procurement_account_id}")
        else:
            logger.info(f"Account already exists: {procurement_account_id}")

async def handle_entitlement_creation_requested(payload, session: AsyncSession):
    entitlement = payload.get('entitlement', {})
    subscription_id = entitlement.get('id')
    if not subscription_id:
        logger.error("No subscription ID found in the message.")
        return

    # Fetch the entitlement details to get the associated account ID and plan details
    entitlement_details = await fetch_entitlement_details(subscription_id)
    procurement_account_id = entitlement_details.get('account').split('/')[-1]
    product_id = entitlement_details.get('product')
    plan_id = entitlement_details.get('plan')
    consumer_id = entitlement_details.get('usageReportingId')
    start_time = entitlement_details.get('createTime')

    # Convert start_time to datetime object
    start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    start_time_naive = start_time.replace(tzinfo=None)

    async with session.begin():
        result = await session.execute(select(Account).filter(Account.procurement_account_id == procurement_account_id))
        db_account = result.scalars().first()
        if db_account:
            result = await session.execute(select(Subscription).filter(Subscription.subscription_id == subscription_id))
            db_subscription = result.scalars().first()
            if not db_subscription:
                db_subscription = Subscription(
                    account_id=db_account.id,
                    subscription_id=subscription_id,
                    product_id=product_id,
                    plan_id=plan_id,
                    consumer_id=consumer_id,
                    start_time=start_time_naive,
                    status='pending'
                )
                session.add(db_subscription)
            else:
                db_subscription.product_id = product_id
                db_subscription.plan_id = plan_id
                db_subscription.consumer_id = consumer_id
                db_subscription.start_time = start_time_naive
                db_subscription.status = "pending"
            db_account.plan_id = plan_id
            db_account.start_time = start_time_naive
            db_account.consumer_id = consumer_id
            await session.commit()
            logger.info(f"Entitlement creation requested: {subscription_id}")
        else:
            # Store the entitlement with a reference to the account but don't approve it yet
            db_subscription = Subscription(
                subscription_id=subscription_id,
                product_id=product_id,
                plan_id=plan_id,
                consumer_id=consumer_id,
                start_time=start_time_naive,
                status='pending'
            )
            session.add(db_subscription)
            await session.commit()
            logger.info(f"Entitlement stored for later approval: {subscription_id}")

async def handle_entitlement_active(payload, session: AsyncSession):
    entitlement = payload.get('entitlement', {})
    subscription_id = entitlement.get('id')
    if not subscription_id:
        logger.error("No subscription ID found in the message.")
        return

    async with session.begin():
        result = await session.execute(select(Subscription).filter(Subscription.subscription_id == subscription_id))
        db_subscription = result.scalars().first()
        if db_subscription:
            db_subscription.status = "active"
            await session.commit()
            logger.info(f"Entitlement activated: {subscription_id}")
            # Set up resources for the customer here
        else:
            logger.error(f"No subscription found for ID {subscription_id} to activate.")

async def handle_entitlement_cancelled(payload, session: AsyncSession):
    entitlement = payload.get('entitlement', {})
    subscription_id = entitlement.get('id')
    if not subscription_id:
        logger.error("No subscription ID found in the message.")
        return

    try:
        async with session.begin():
            result = await session.execute(select(Subscription).filter(Subscription.subscription_id == subscription_id))
            db_subscription = result.scalars().first()
            if db_subscription:
                # Update the subscription status
                db_subscription.status = "canceled"
                await session.commit()
                logger.info(f"Entitlement canceled: {subscription_id}")

                # Update the parent account status
                result = await session.execute(select(Account).filter(Account.id == db_subscription.account_id))
                account = result.scalars().first()
                if account:
                    account.status = "entitlement canceled"
                    await session.commit()
                    logger.info(f"Account status updated to 'entitlement canceled': {account.procurement_account_id}")
                else:
                    logger.error(f"No account found for ID {db_subscription.account_id} to update status.")
            else:
                logger.error(f"No subscription found for ID {subscription_id} to cancel.")
    except Exception as e:
        logger.error(f"Failed to cancel entitlement {subscription_id}: {e}")

async def handle_account_approved(procurement_account_id, session: AsyncSession):
    """Handles account approval and related entitlement approvals."""
    async with session.begin():
        result = await session.execute(select(Account).filter(Account.procurement_account_id == procurement_account_id))
        db_account = result.scalars().first()
        if db_account and db_account.status == 'active':
            # Approve all pending entitlements for this account
            result = await session.execute(select(Subscription).filter(Subscription.account_id == db_account.id, Subscription.status == 'pending'))
            pending_entitlements = result.scalars().all()
            for entitlement in pending_entitlements:
                try:
                    await approve_entitlement(entitlement.subscription_id)
                    entitlement.status = 'active'
                    await session.commit()
                    logger.info(f"Entitlement approved: {entitlement.subscription_id}")
                except Exception as e:
                    logger.error(f"Failed to approve entitlement {entitlement.subscription_id}: {e}")
        else:
            logger.error(f"No active account found for ID {procurement_account_id} to approve entitlements.")
        
async def handle_entitlement_deleted(payload, session: AsyncSession):
    entitlement = payload.get('entitlement', {})
    subscription_id = entitlement.get('id')
    if not subscription_id:
        logger.error("No subscription ID found in the message.")
        return

    try:
        async with session.begin():
            result = await session.execute(select(Subscription).filter(Subscription.subscription_id == subscription_id))
            db_subscription = result.scalars().first()
            if db_subscription:
                await session.delete(db_subscription)
                await session.commit()
                logger.info(f"Entitlement deleted: {subscription_id}")
            else:
                logger.error(f"No subscription found for ID {subscription_id} to delete.")
    except Exception as e:
        logger.error(f"Failed to delete entitlement {subscription_id}: {e}")

async def handle_account_deleted(payload, session: AsyncSession):
    account_details = payload.get('account', {})
    procurement_account_id = account_details.get('id')
    if not procurement_account_id:
        logger.error("No procurement account ID found in the message.")
        return

    try:
        async with session.begin():
            result = await session.execute(select(Account).filter(Account.procurement_account_id == procurement_account_id))
            db_account = result.scalars().first()
            if db_account:
                # Delete all related subscriptions first
                await session.execute(delete(Subscription).filter(Subscription.account_id == db_account.id))
                await session.delete(db_account)
                await session.commit()
                logger.info(f"Account deleted: {procurement_account_id}")
            else:
                logger.error(f"No account found for ID {procurement_account_id} to delete.")
    except Exception as e:
        logger.error(f"Failed to delete account {procurement_account_id}: {e}")
        
async def handle_entitlement_plan_change_requested(payload, session: AsyncSession):
    entitlement = payload.get('entitlement', {})
    subscription_id = entitlement.get('id')
    new_plan = entitlement.get('newPlan')
    if not subscription_id or not new_plan:
        logger.error("No subscription ID or new plan found in the message.")
        return

    logger.debug(f"Processing plan change request for subscription ID: {subscription_id} to new plan: {new_plan}")

    try:
        # Update the subscription in the local database
        async with session.begin():
            result = await session.execute(select(Subscription).filter(Subscription.subscription_id == subscription_id))
            db_subscription = result.scalars().first()
            if db_subscription:
                db_subscription.plan_id = new_plan
                db_subscription.status = "plan change requested"
                await session.commit()
                logger.info(f"Entitlement plan change requested: {subscription_id} to new plan {new_plan}")

                result = await session.execute(select(Account).filter(Account.id == db_subscription.account_id))
                account = result.scalars().first()
                if account:
                    account.plan_id = new_plan
                    await session.commit()
                    logger.info(f"Account plan updated: {account.procurement_account_id}")
                
                # Approve the plan change in the procurement API
                await approve_entitlement_plan_change(subscription_id, new_plan)
            else:
                logger.error(f"No subscription found for ID {subscription_id} to change plan.")
    except Exception as e:
        logger.error(f"Failed to process plan change for entitlement {subscription_id}: {e}")

async def handle_entitlement_plan_changed(payload, session: AsyncSession):
    entitlement = payload.get('entitlement', {})
    subscription_id = entitlement.get('id')
    if not subscription_id:
        logger.error("No subscription ID found in the message.")
        return

    logger.debug(f"Activating plan change for subscription ID: {subscription_id}")

    try:
        async with session.begin():
            result = await session.execute(select(Subscription).filter(Subscription.subscription_id == subscription_id))
            db_subscription = result.scalars().first()
            if db_subscription:
                db_subscription.status = "active"
                await session.commit()
                logger.info(f"Entitlement plan changed and activated: {subscription_id}")
            else:
                logger.error(f"No subscription found for ID {subscription_id} to activate.")
    except Exception as e:
        logger.error(f"Failed to activate entitlement plan change for {subscription_id}: {e}")

async def approve_entitlement_plan_change(entitlement_id, new_plan):
    """Approves the entitlement plan change in the Procurement Service."""
    name = f'providers/{PROJECT_ID}/entitlements/{entitlement_id}:approvePlanChange'
    body = {'pendingPlanName': new_plan}
    logger.debug(f"Approving plan change for entitlement ID: {entitlement_id} with body: {body}")
    request = service.providers().entitlements().approvePlanChange(name=name, body=body)
    request.execute()
    logger.info(f"Plan change approved for entitlement: {entitlement_id} to plan: {new_plan}")

async def callback(message):
    payload = json.loads(message.data)
    logger.info(f"Received message: {payload}")
    
    event_type = payload.get("eventType", "")
    
    async with AsyncSessionLocal() as session:
        try:
            event_handlers = {
                "ACCOUNT_ACTIVE": handle_account_created,
                "ENTITLEMENT_CREATION_REQUESTED": handle_entitlement_creation_requested,
                "ENTITLEMENT_ACTIVE": handle_entitlement_active,
                "ENTITLEMENT_CANCELLED": handle_entitlement_cancelled,
                "ENTITLEMENT_DELETED": handle_entitlement_deleted,
                "ACCOUNT_DELETED": handle_account_deleted,
                "ENTITLEMENT_PLAN_CHANGE_REQUESTED": handle_entitlement_plan_change_requested,
                "ENTITLEMENT_PLAN_CHANGED": handle_entitlement_plan_changed,
            }

            handler = event_handlers.get(event_type)
            if handler:
                await handler(payload, session)
            else:
                logger.error(f"Unknown event type for message: {payload}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    message.ack()

async def subscribe_to_pubsub():
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path('landgriffon', PUBSUB_SUBSCRIPTION)

    # Debugging statement to verify the subscription path
    logger.info(f'Subscription path: {subscription_path}')
    
    loop = asyncio.get_event_loop()

    def wrapped_callback(message):
        asyncio.run_coroutine_threadsafe(callback(message), loop)

    streaming_pull_future = subscriber.subscribe(subscription_path, callback=wrapped_callback)
    logger.info(f'Listening for messages on {subscription_path}')

    try:
        await asyncio.get_event_loop().run_in_executor(None, streaming_pull_future.result)
    except Exception as e:
        streaming_pull_future.cancel()
        logger.error(f'Listening for messages on {subscription_path} threw an Exception: {e}')
