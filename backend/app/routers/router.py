import os
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime
from fastapi.responses import RedirectResponse
import httpx
import jwt
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Account, Subscription
from pydantic import BaseModel
from app.pubsub import approve_account, handle_account_approved, approve_entitlement, fetch_entitlement_details, _generate_internal_account_id
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

JWT_ISSUER = "https://www.googleapis.com/robot/v1/metadata/x509/cloud-commerce-partner@system.gserviceaccount.com"
JWT_AUDIENCE = os.getenv("PARTNER_DOMAIN_NAME")

# Schemas
class JWTData(BaseModel):
    iss: str
    iat: int
    exp: int
    aud: str
    sub: str
    google: dict

def get_google_public_key(kid):
    response = httpx.get(JWT_ISSUER)
    response.raise_for_status()
    keys = response.json()
    return keys[kid]

def validate_jwt(token):
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header["kid"]
    public_key = get_google_public_key(kid)

    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    return JWTData(**payload)
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
        from_attributes = True

# Account Endpoints
@router.post("/signup")
def signup(request: Request, db: Session = Depends(get_db)):
    token = request.headers.get("x-gcp-marketplace-token")
    if not token:
        raise HTTPException(status_code=400, detail="Missing JWT token")

    jwt_data = validate_jwt(token)
    
    procurement_account_id = jwt_data.sub

    account = db.query(Account).filter(Account.procurement_account_id == procurement_account_id).first()
    if not account:
        internal_account_id = _generate_internal_account_id()
        account = Account(
            procurement_account_id=procurement_account_id,
            internal_account_id=internal_account_id,
            status='pending'
        )
        db.add(account)
    db.commit()

    try:
        # Use the existing function to approve the account
        approve_account_endpoint(procurement_account_id, db)
        logger.info(f"Account approved successfully for procurement_account_id: {procurement_account_id}")
        return RedirectResponse(url="/success")  # Change "/success" to your desired redirect URL
    except Exception as e:
        logger.error(f"Failed to approve account: {e}")
        return RedirectResponse(url=f"/failure?reason={str(e)}")


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

@router.post("/subscriptions/{subscription_id}/approve")
def approve_subscription_endpoint(subscription_id: str, db: Session = Depends(get_db)):
    subscription = db.query(Subscription).filter(Subscription.subscription_id == subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    try:
        # Fetch the entitlement details to get the associated account ID and plan details
        entitlement_details = fetch_entitlement_details(subscription_id)
        procurement_account_id = entitlement_details.get('account').split('/')[-1]
        plan_id = entitlement_details.get('plan')
        start_time = entitlement_details.get('createTime')
        consumer_id = entitlement_details.get('usageReportingId')

        # Convert start_time to datetime object
        start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))

        # Update the account with the new plan_id, start_time, and consumer_id
        account = db.query(Account).filter(Account.procurement_account_id == procurement_account_id).first()
        if account:
            account.plan_id = plan_id
            account.start_time = start_time
            account.consumer_id = consumer_id
            db.commit()

        # Approve the entitlement
        approve_entitlement(subscription_id)
        subscription.status = 'active'
        db.commit()
        logger.info(f"Entitlement approved: {subscription_id}")
        return {"message": "Subscription approved successfully"}
    except Exception as e:
        logger.error(f"Failed to approve subscription: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to approve subscription: {e}")
    
@router.post("/recover_and_approve_account/{subscription_id}")
def recover_and_approve_account(subscription_id: str, db: Session = Depends(get_db)):
    try:
        # Fetch entitlement details and related account details
        entitlement_details = fetch_entitlement_details(subscription_id)
        procurement_account_id = entitlement_details.get('account').split('/')[-1]
        plan_id = entitlement_details.get('plan')
        consumer_id = entitlement_details.get('usageReportingId')
        start_time = entitlement_details.get('createTime')
        
        # Convert start_time to datetime object
        start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        
        # Create or update account
        account = db.query(Account).filter(Account.procurement_account_id == procurement_account_id).first()
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
        db.commit()
        
        # Approve the account
        approve_account(procurement_account_id)
        
        # Update account status to active
        account.status = 'active'
        db.commit()
        
        # Approve the related entitlement
        approve_entitlement(subscription_id)
        
        return {"message": "Account and related entitlement approved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to recover and approve account: {e}")

