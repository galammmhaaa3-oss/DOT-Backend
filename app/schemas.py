from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from .models import UserRole, OrderType, OrderStatus, TransactionType


# ============ Auth Schemas ============
class UserCreate(BaseModel):
    phone: str
    email: Optional[str] = None
    name: str
    password: str
    role: UserRole = UserRole.CUSTOMER


class UserLogin(BaseModel):
    phone: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: Optional[int] = None
    role: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    phone: str
    email: Optional[str]
    name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============ Wallet Schemas ============
class WalletResponse(BaseModel):
    id: int
    user_id: int
    balance: float
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WalletTopUp(BaseModel):
    driver_id: int
    amount: float
    admin_id: int


class TransactionResponse(BaseModel):
    id: int
    wallet_id: int
    type: TransactionType
    amount: float
    description: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============ Order Schemas ============
class LocationData(BaseModel):
    latitude: float
    longitude: float
    address: Optional[str] = None


class TaxiOrderCreate(BaseModel):
    pickup: LocationData
    dropoff: LocationData


class DeliveryOrderCreate(BaseModel):
    pickup: LocationData
    dropoff: LocationData
    recipient_name: str
    recipient_phone: str
    item_description: str
    item_price: Optional[float] = 0


class OrderResponse(BaseModel):
    id: int
    type: OrderType
    status: OrderStatus
    customer_id: int
    driver_id: Optional[int]
    pickup_lat: float
    pickup_lng: float
    pickup_address: Optional[str]
    dropoff_lat: float
    dropoff_lng: float
    dropoff_address: Optional[str]
    estimated_price: Optional[float]
    final_price: Optional[float]
    recipient_name: Optional[str]
    recipient_phone: Optional[str]
    item_description: Optional[str]
    item_price: Optional[float]
    created_at: datetime
    
    class Config:
        from_attributes = True


class OrderAccept(BaseModel):
    order_id: int
    driver_id: int


class OrderUpdateStatus(BaseModel):
    order_id: int
    status: OrderStatus
    notes: Optional[str] = None


class OrderCancel(BaseModel):
    order_id: int
    reason: str


# ============ Rating Schemas ============
class RatingCreate(BaseModel):
    order_id: int
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class RatingResponse(BaseModel):
    id: int
    order_id: int
    customer_id: int
    driver_id: int
    rating: int
    comment: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============ Driver Location ============
class LocationUpdate(BaseModel):
    latitude: float
    longitude: float


# ============ Settings Schemas ============
class SettingUpdate(BaseModel):
    key: str
    value: str


class SettingResponse(BaseModel):
    id: int
    key: str
    value: str
    description: Optional[str]
    
    class Config:
        from_attributes = True


# ============ City Schemas ============
class CityCreate(BaseModel):
    name: str
    name_ar: str
    base_price: float
    price_per_km: float


class CityResponse(BaseModel):
    id: int
    name: str
    name_ar: str
    is_active: bool
    base_price: float
    price_per_km: float
    
    class Config:
        from_attributes = True


# ============ Admin Schemas ============
class DriverStats(BaseModel):
    driver_id: int
    driver_name: str
    total_orders: int
    completed_orders: int
    cancelled_orders: int
    average_rating: float
    wallet_balance: float


class OrderLog(BaseModel):
    order_id: int
    type: OrderType
    status: OrderStatus
    customer_name: str
    driver_name: Optional[str]
    created_at: datetime
    accepted_at: Optional[datetime]
    completed_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    cancellation_reason: Optional[str]


# ============ WebSocket Messages ============
class WSMessage(BaseModel):
    type: str
    data: dict


class DriverLocationWS(BaseModel):
    driver_id: int
    latitude: float
    longitude: float
    timestamp: datetime


class OrderUpdateWS(BaseModel):
    order_id: int
    status: OrderStatus
    message: str
