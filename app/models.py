from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
from .database import Base


class UserRole(str, enum.Enum):
    CUSTOMER = "customer"
    DRIVER = "driver"
    ADMIN = "admin"


class OrderType(str, enum.Enum):
    TAXI = "taxi"
    DELIVERY = "delivery"


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TransactionType(str, enum.Enum):
    TOP_UP = "top_up"
    DEDUCTION = "deduction"
    REFUND = "refund"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, nullable=True)  # Email field added
    name = Column(String, nullable=False)
    role = Column(Enum(UserRole, native_enum=False, length=50), default=UserRole.CUSTOMER)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    orders = relationship("Order", back_populates="customer", foreign_keys="Order.customer_id")
    driver_orders = relationship("Order", back_populates="driver", foreign_keys="Order.driver_id")
    wallet = relationship("Wallet", back_populates="user", uselist=False)
    ratings_given = relationship("Rating", back_populates="customer", foreign_keys="Rating.customer_id")
    ratings_received = relationship("Rating", back_populates="driver", foreign_keys="Rating.driver_id")


class Wallet(Base):
    __tablename__ = "wallets"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    balance = Column(Float, default=0.0)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="wallet")
    transactions = relationship("Transaction", back_populates="wallet")


class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"))
    type = Column(Enum(TransactionType, native_enum=False, length=50), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(String)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    wallet = relationship("Wallet", back_populates="transactions")
    order = relationship("Order", back_populates="transaction")


class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    type = Column(Enum(OrderType, native_enum=False, length=50), nullable=False)
    status = Column(Enum(OrderStatus, native_enum=False, length=50), default=OrderStatus.PENDING)
    
    # Customer
    customer_id = Column(Integer, ForeignKey("users.id"))
    
    # Driver
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Locations
    pickup_lat = Column(Float, nullable=False)
    pickup_lng = Column(Float, nullable=False)
    pickup_address = Column(String)
    
    dropoff_lat = Column(Float, nullable=False)
    dropoff_lng = Column(Float, nullable=False)
    dropoff_address = Column(String)
    
    # Pricing
    estimated_price = Column(Float)
    final_price = Column(Float, nullable=True)
    commission = Column(Float)
    
    # Delivery specific fields
    recipient_name = Column(String, nullable=True)
    recipient_phone = Column(String, nullable=True)
    item_description = Column(String, nullable=True)
    item_price = Column(Float, nullable=True)  # If cash collection needed
    recipient_location_token = Column(String, nullable=True)  # For location link
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    picked_up_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_reason = Column(String, nullable=True)
    cancelled_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    customer = relationship("User", back_populates="orders", foreign_keys=[customer_id])
    driver = relationship("User", back_populates="driver_orders", foreign_keys=[driver_id])
    rating = relationship("Rating", back_populates="order", uselist=False)
    transaction = relationship("Transaction", back_populates="order", uselist=False)
    status_logs = relationship("OrderStatusLog", back_populates="order")


class OrderStatusLog(Base):
    """Log every status change for dispute resolution"""
    __tablename__ = "order_status_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    old_status = Column(Enum(OrderStatus, native_enum=False, length=50))
    new_status = Column(Enum(OrderStatus, native_enum=False, length=50))
    changed_by = Column(Integer, ForeignKey("users.id"))
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(Text, nullable=True)
    
    # Relationships
    order = relationship("Order", back_populates="status_logs")


class Rating(Base):
    __tablename__ = "ratings"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), unique=True)
    customer_id = Column(Integer, ForeignKey("users.id"))
    driver_id = Column(Integer, ForeignKey("users.id"))
    rating = Column(Integer, nullable=False)  # 1-5
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    order = relationship("Order", back_populates="rating")
    customer = relationship("User", back_populates="ratings_given", foreign_keys=[customer_id])
    driver = relationship("User", back_populates="ratings_received", foreign_keys=[driver_id])


class Settings(Base):
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String, nullable=False)
    description = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


class City(Base):
    """Support for multiple cities/regions"""
    __tablename__ = "cities"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    name_ar = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    base_price = Column(Float)  # Base price for this city
    price_per_km = Column(Float)  # Price per kilometer
    created_at = Column(DateTime(timezone=True), server_default=func.now())
