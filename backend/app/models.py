from sqlalchemy import Column, Integer, String, JSON
from app.database import Base

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(String, unique=True, index=True)
    data = Column(JSON)
