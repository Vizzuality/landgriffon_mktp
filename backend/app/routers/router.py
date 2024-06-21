from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Account, Subscription
from pydantic import BaseModel
from app.pubsub import approve_account, handle_account_approved

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
        from_attributes = True  # Update to comply with Pydantic v2

class AccountSchema(BaseModel):
    procurement_account_id: str
    internal_account_id: str
    status: str

    class Config:
        from_attributes = True  # Update to comply with Pydantic v2

# Account Endpoints
@router.post("/accounts/{procurement_account_id}/approve", response_model=AccountApprovalSchema)
def approve_account_endpoint(procurement_account_id: str, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.procurement_account_id == procurement_account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if account.status != 'pending':
        raise HTTPException(status_code=400, detail="Account is not in a pending state")
    
    try:
        approve_account(procurement_account_id)
        account.status = 'active'
        db.commit()
        handle_account_approved(procurement_account_id, db)  # Approve related entitlements
        return account
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to approve account: {e}")

@router.get("/accounts", response_model=list[AccountSchema])
def get_accounts(db: Session = Depends(get_db)):
    return db.query(Account).all()

@router.get("/accounts/{account_id}", response_model=AccountSchema)
def get_account(account_id: str, db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.procurement_account_id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account

# Subscription Endpoints
@router.get("/subscriptions", response_model=list[SubscriptionSchema])
def get_subscriptions(db: Session = Depends(get_db)):
    return db.query(Subscription).all()

@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionSchema)
def get_subscription(subscription_id: str, db: Session = Depends(get_db)):
    subscription = db.query(Subscription).filter(Subscription.subscription_id == subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription
