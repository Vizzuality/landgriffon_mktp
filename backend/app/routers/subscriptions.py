from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Subscription
from pydantic import BaseModel

router = APIRouter()

class SubscriptionSchema(BaseModel):
    subscription_id: str
    data: dict
    status: str  # Include the status field

    class Config:
        from_attributes = True  # Update to comply with Pydantic v2

@router.get("/subscriptions", response_model=list[SubscriptionSchema])
def get_subscriptions(db: Session = Depends(get_db)):
    return db.query(Subscription).all()

@router.post("/subscriptions/{subscription_id}/approve", response_model=SubscriptionSchema)
def approve_subscription(subscription_id: str, db: Session = Depends(get_db)):
    subscription = db.query(Subscription).filter(Subscription.subscription_id == subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    subscription.status = "approved"
    db.commit()
    db.refresh(subscription)
    return subscription
