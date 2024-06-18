from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Subscription
from pydantic import BaseModel

router = APIRouter()

class SubscriptionSchema(BaseModel):
    subscription_id: str
    data: dict

    class Config:
        from_attributes = True  # Update to comply with Pydantic v2

@router.get("/subscriptions", response_model=list[SubscriptionSchema])
def get_subscriptions(db: Session = Depends(get_db)):
    return db.query(Subscription).all()

@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionSchema)
def get_subscription(subscription_id: str, db: Session = Depends(get_db)):
    subscription = db.query(Subscription).filter(Subscription.subscription_id == subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription

@router.post("/subscriptions", response_model=SubscriptionSchema)
def create_subscription(subscription: SubscriptionSchema, db: Session = Depends(get_db)):
    db_subscription = Subscription(subscription_id=subscription.subscription_id, data=subscription.data)
    db.add(db_subscription)
    db.commit()
    db.refresh(db_subscription)
    return db_subscription

@router.delete("/subscriptions/{subscription_id}")
def delete_subscription(subscription_id: str, db: Session = Depends(get_db)):
    subscription = db.query(Subscription).filter(Subscription.subscription_id == subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    db.delete(subscription)
    db.commit()
    return {"message": "Subscription deleted"}

@router.put("/subscriptions/{subscription_id}", response_model=SubscriptionSchema)
def update_subscription(subscription_id: str, subscription: SubscriptionSchema, db: Session = Depends(get_db)):
    db_subscription = db.query(Subscription).filter(Subscription.subscription_id == subscription_id).first()
    if not db_subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    db_subscription.data = subscription.data
    db.commit()
    db.refresh(db_subscription)
    return db_subscription
