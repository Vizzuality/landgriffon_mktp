from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.models import Account, Subscription
from pydantic import BaseModel
from app.pubsub import approve_account, handle_account_approved, approve_entitlement, fetch_entitlement_details, _generate_internal_account_id
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Schemas
class AccountApprovalSchema(BaseModel):
    internal_account_id: str

class SubscriptionSchema(BaseModel):
    subscription_id: str
    product_id: str
    plan_id: str
    consumer_id: str
    start_time: str  # You may want to use datetime if needed
    status: str  # Include the status field

    class Config:
        from_attributes = True

class AccountSchema(BaseModel):
    procurement_account_id: str
    internal_account_id: str
    status: str

    class Config:
        orm_mode = True

# Account Endpoints
@router.post("/accounts/{procurement_account_id}/approve", response_model=AccountApprovalSchema)
async def approve_account_endpoint(procurement_account_id: str, db: AsyncSession = Depends(get_db)):
    async with db.begin():
        result = await db.execute(select(Account).filter(Account.procurement_account_id == procurement_account_id))
        account = result.scalars().first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        if account.status != 'pending':
            raise HTTPException(status_code=400, detail="Account is not in a pending state")
        
        try:
            await approve_account(procurement_account_id)
            account.status = 'active'
            await db.commit()

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to approve account: {e}")

    try:
        async with db.begin():
            await handle_account_approved(procurement_account_id, db)  # Approve related entitlements
        return account
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to approve account: {e}")

@router.get("/accounts", response_model=list[AccountSchema])
async def get_accounts(db: AsyncSession = Depends(get_db)):
    async with db.begin():
        result = await db.execute(select(Account))
        accounts = result.scalars().all()
        return accounts

@router.get("/accounts/{account_id}", response_model=AccountSchema)
async def get_account(account_id: str, db: AsyncSession = Depends(get_db)):
    async with db.begin():
        result = await db.execute(select(Account).filter(Account.procurement_account_id == account_id))
        account = result.scalars().first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        return account

# Subscription Endpoints
@router.get("/subscriptions", response_model=list[SubscriptionSchema])
async def get_subscriptions(db: AsyncSession = Depends(get_db)):
    async with db.begin():
        result = await db.execute(select(Subscription))
        subscriptions = result.scalars().all()
        return subscriptions

@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionSchema)
async def get_subscription(subscription_id: str, db: AsyncSession = Depends(get_db)):
    async with db.begin():
        result = await db.execute(select(Subscription).filter(Subscription.subscription_id == subscription_id))
        subscription = result.scalars().first()
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")
        return subscription

@router.post("/subscriptions/{subscription_id}/approve")
async def approve_subscription_endpoint(subscription_id: str, db: AsyncSession = Depends(get_db)):
    async with db.begin():
        result = await db.execute(select(Subscription).filter(Subscription.subscription_id == subscription_id))
        subscription = result.scalars().first()
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        try:
            # Fetch the entitlement details to get the associated account ID and plan details
            entitlement_details = await fetch_entitlement_details(subscription_id)
            procurement_account_id = entitlement_details.get('account').split('/')[-1]
            plan_id = entitlement_details.get('plan')
            start_time = entitlement_details.get('createTime')
            consumer_id = entitlement_details.get('usageReportingId')
            state = entitlement_details.get('state')

            # Log the entitlement details for debugging
            logger.info(f"Entitlement details: {entitlement_details}")

            if state != 'ENTITLEMENT_ACTIVATION_REQUESTED':
                logger.error(f"Entitlement state is {state}, cannot approve")
                raise HTTPException(status_code=400, detail=f"Entitlement state is {state}, cannot approve")

            # Convert start_time to datetime object and make it naive
            start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            start_time = start_time.replace(tzinfo=None)  # Make the datetime naive

            # Update the account with the new plan_id, start_time, and consumer_id
            result = await db.execute(select(Account).filter(Account.procurement_account_id == procurement_account_id))
            account = result.scalars().first()
            if account:
                account.plan_id = plan_id
                account.start_time = start_time
                account.consumer_id = consumer_id
                await db.commit()

            # Log the approval request details
            logger.info(f"Approving entitlement with ID: {subscription_id}")

            # Approve the entitlement
            await approve_entitlement(subscription_id)

            # Update subscription status
            subscription.status = 'active'
            await db.commit()

            logger.info(f"Entitlement approved: {subscription_id}")
            return {"message": "Subscription approved successfully"}
        except Exception as e:
            logger.error(f"Failed to approve subscription: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to approve subscription: {e}")

    
@router.post("/recover_and_approve_account/{subscription_id}")
async def recover_and_approve_account(subscription_id: str, db: AsyncSession = Depends(get_db)):
    try:
        # Fetch entitlement details and related account details
        entitlement_details = await fetch_entitlement_details(subscription_id)
        procurement_account_id = entitlement_details.get('account').split('/')[-1]
        plan_id = entitlement_details.get('plan')
        consumer_id = entitlement_details.get('usageReportingId')
        start_time = entitlement_details.get('createTime')
        
        # Convert start_time to datetime object
        start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        start_time = start_time.replace(tzinfo=None)
        
        # Create or update account
        async with db.begin():
            result = await db.execute(select(Account).filter(Account.procurement_account_id == procurement_account_id))
            account = result.scalars().first()
            if not account:
                internal_account_id = _generate_internal_account_id()
                account = Account(
                    procurement_account_id=procurement_account_id,
                    internal_account_id=internal_account_id,
                    status='pending',
                    plan_id=plan_id,
                    start_time=start_time,
                    consumer_id=consumer_id
                )
                db.add(account)
            else:
                account.plan_id = plan_id
                account.start_time = start_time
                account.consumer_id = consumer_id
                account.status = 'pending'
            await db.commit()
        
        # Approve the account
        await approve_account(procurement_account_id)
        
        # Update account status to active
        async with db.begin():
            result = await db.execute(select(Account).filter(Account.procurement_account_id == procurement_account_id))
            account = result.scalars().first()
            if account:
                account.status = 'active'
                await db.commit()
        
        # Approve the related entitlement
        await approve_entitlement(subscription_id)
        
        return {"message": "Account and related entitlement approved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to recover and approve account: {e}")
