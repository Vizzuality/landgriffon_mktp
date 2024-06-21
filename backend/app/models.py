from sqlalchemy import Column, Integer, String, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    procurement_account_id = Column(String, unique=True, index=True)
    internal_account_id = Column(String, unique=True, index=True)
    status = Column(String, default='pending')
    start_time = Column(TIMESTAMP)
    plan_id = Column(String)
    consumer_id = Column(String)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)
    subscriptions = relationship("Subscription", back_populates="account")

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey('accounts.id'))
    subscription_id = Column(String, unique=True, index=True)
    product_id = Column(String)
    plan_id = Column(String)
    consumer_id = Column(String)
    start_time = Column(TIMESTAMP)
    status = Column(String)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)
    account = relationship("Account", back_populates="subscriptions")
