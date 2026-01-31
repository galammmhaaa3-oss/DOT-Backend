from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import List
from datetime import datetime
import secrets
from ..database import get_db
from ..models import Order, OrderType, OrderStatus, OrderStatusLog, User
from ..schemas import (
    TaxiOrderCreate,
    DeliveryOrderCreate,
    OrderResponse,
    OrderAccept,
    OrderUpdateStatus,
    OrderCancel
)
from ..auth import get_current_user, get_current_driver
from ..services.maps_service import maps_service
from ..services.sms_service import sms_service
from ..services.wallet_service import wallet_service
from ..config import settings

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/taxi", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_taxi_order(
    order_data: TaxiOrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new taxi ride request"""
    
    # Calculate estimated price
    estimated_price = await maps_service.calculate_price(
        order_data.pickup.latitude,
        order_data.pickup.longitude,
        order_data.dropoff.latitude,
        order_data.dropoff.longitude
    )
    
    if not estimated_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not calculate distance"
        )
    
    # Get addresses if not provided
    pickup_address = order_data.pickup.address
    if not pickup_address:
        pickup_address = await maps_service.reverse_geocode(
            order_data.pickup.latitude,
            order_data.pickup.longitude
        )
    
    dropoff_address = order_data.dropoff.address
    if not dropoff_address:
        dropoff_address = await maps_service.reverse_geocode(
            order_data.dropoff.latitude,
            order_data.dropoff.longitude
        )
    
    # Create order
    new_order = Order(
        type=OrderType.TAXI,
        customer_id=current_user.id,
        pickup_lat=order_data.pickup.latitude,
        pickup_lng=order_data.pickup.longitude,
        pickup_address=pickup_address,
        dropoff_lat=order_data.dropoff.latitude,
        dropoff_lng=order_data.dropoff.longitude,
        dropoff_address=dropoff_address,
        estimated_price=estimated_price,
        commission=settings.DEFAULT_COMMISSION
    )
    
    db.add(new_order)
    await db.commit()
    await db.refresh(new_order)
    
    # Log status
    status_log = OrderStatusLog(
        order_id=new_order.id,
        old_status=None,
        new_status=OrderStatus.PENDING,
        changed_by=current_user.id
    )
    db.add(status_log)
    await db.commit()
    
    return new_order


@router.post("/delivery", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_delivery_order(
    order_data: DeliveryOrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new delivery request"""
    
    # Calculate estimated price
    estimated_price = await maps_service.calculate_price(
        order_data.pickup.latitude,
        order_data.pickup.longitude,
        order_data.dropoff.latitude,
        order_data.dropoff.longitude
    )
    
    if not estimated_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not calculate distance"
        )
    
    # Generate unique token for recipient location submission
    location_token = secrets.token_urlsafe(32)
    
    # Get addresses
    pickup_address = order_data.pickup.address
    if not pickup_address:
        pickup_address = await maps_service.reverse_geocode(
            order_data.pickup.latitude,
            order_data.pickup.longitude
        )
    
    dropoff_address = order_data.dropoff.address
    if not dropoff_address:
        dropoff_address = await maps_service.reverse_geocode(
            order_data.dropoff.latitude,
            order_data.dropoff.longitude
        )
    
    # Create order
    new_order = Order(
        type=OrderType.DELIVERY,
        customer_id=current_user.id,
        pickup_lat=order_data.pickup.latitude,
        pickup_lng=order_data.pickup.longitude,
        pickup_address=pickup_address,
        dropoff_lat=order_data.dropoff.latitude,
        dropoff_lng=order_data.dropoff.longitude,
        dropoff_address=dropoff_address,
        estimated_price=estimated_price,
        commission=settings.DEFAULT_COMMISSION,
        recipient_name=order_data.recipient_name,
        recipient_phone=order_data.recipient_phone,
        item_description=order_data.item_description,
        item_price=order_data.item_price,
        recipient_location_token=location_token
    )
    
    db.add(new_order)
    await db.commit()
    await db.refresh(new_order)
    
    # Log status
    status_log = OrderStatusLog(
        order_id=new_order.id,
        old_status=None,
        new_status=OrderStatus.PENDING,
        changed_by=current_user.id
    )
    db.add(status_log)
    await db.commit()
    
    # Send SMS to recipient with location link
    await sms_service.send_location_link(
        order_data.recipient_phone,
        location_token,
        new_order.id
    )
    
    return new_order


@router.get("/pending", response_model=List[OrderResponse])
async def get_pending_orders(
    current_driver: User = Depends(get_current_driver),
    db: AsyncSession = Depends(get_db)
):
    """Get all pending orders for drivers"""
    
    # Check if driver can accept orders (has sufficient balance)
    can_accept = await wallet_service.can_accept_orders(db, current_driver.id)
    if not can_accept:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient wallet balance. Please top up your wallet."
        )
    
    result = await db.execute(
        select(Order)
        .filter(Order.status == OrderStatus.PENDING)
        .order_by(Order.created_at.desc())
    )
    
    return result.scalars().all()


@router.post("/accept", response_model=OrderResponse)
async def accept_order(
    accept_data: OrderAccept,
    current_driver: User = Depends(get_current_driver),
    db: AsyncSession = Depends(get_db)
):
    """Driver accepts an order"""
    
    # Check wallet balance
    can_accept = await wallet_service.can_accept_orders(db, current_driver.id)
    if not can_accept:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient wallet balance"
        )
    
    # Get order
    result = await db.execute(
        select(Order).filter(Order.id == accept_data.order_id)
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.status != OrderStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order is not available"
        )
    
    # Update order
    old_status = order.status
    order.driver_id = current_driver.id
    order.status = OrderStatus.ACCEPTED
    order.accepted_at = datetime.utcnow()
    
    # Log status change
    status_log = OrderStatusLog(
        order_id=order.id,
        old_status=old_status,
        new_status=OrderStatus.ACCEPTED,
        changed_by=current_driver.id
    )
    db.add(status_log)
    
    await db.commit()
    await db.refresh(order)
    
    return order


@router.post("/update-status", response_model=OrderResponse)
async def update_order_status(
    update_data: OrderUpdateStatus,
    current_driver: User = Depends(get_current_driver),
    db: AsyncSession = Depends(get_db)
):
    """Update order status (pickup, in transit, delivered, completed)"""
    
    result = await db.execute(
        select(Order).filter(
            and_(
                Order.id == update_data.order_id,
                Order.driver_id == current_driver.id
            )
        )
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    old_status = order.status
    order.status = update_data.status
    
    # Update timestamps based on status
    if update_data.status == OrderStatus.PICKED_UP:
        order.picked_up_at = datetime.utcnow()
    elif update_data.status == OrderStatus.DELIVERED:
        order.delivered_at = datetime.utcnow()
    elif update_data.status == OrderStatus.COMPLETED:
        order.completed_at = datetime.utcnow()
        
        # Deduct commission from driver's wallet
        transaction = await wallet_service.deduct_commission(
            db, current_driver.id, order.id, order.commission
        )
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient wallet balance to complete order"
            )
    
    # Log status change
    status_log = OrderStatusLog(
        order_id=order.id,
        old_status=old_status,
        new_status=update_data.status,
        changed_by=current_driver.id,
        notes=update_data.notes
    )
    db.add(status_log)
    
    await db.commit()
    await db.refresh(order)
    
    return order


@router.post("/cancel", response_model=OrderResponse)
async def cancel_order(
    cancel_data: OrderCancel,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancel an order"""
    
    result = await db.execute(
        select(Order).filter(Order.id == cancel_data.order_id)
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check authorization
    if current_user.id != order.customer_id and current_user.id != order.driver_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    old_status = order.status
    order.status = OrderStatus.CANCELLED
    order.cancelled_at = datetime.utcnow()
    order.cancelled_by = current_user.id
    order.cancellation_reason = cancel_data.reason
    
    # Log status change
    status_log = OrderStatusLog(
        order_id=order.id,
        old_status=old_status,
        new_status=OrderStatus.CANCELLED,
        changed_by=current_user.id,
        notes=cancel_data.reason
    )
    db.add(status_log)
    
    await db.commit()
    await db.refresh(order)
    
    return order


@router.get("/my-orders", response_model=List[OrderResponse])
async def get_my_orders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's order history"""
    
    if current_user.role == "driver":
        result = await db.execute(
            select(Order)
            .filter(Order.driver_id == current_user.id)
            .order_by(Order.created_at.desc())
        )
    else:
        result = await db.execute(
            select(Order)
            .filter(Order.customer_id == current_user.id)
            .order_by(Order.created_at.desc())
        )
    
    return result.scalars().all()


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get order details"""
    
    result = await db.execute(
        select(Order).filter(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check authorization
    if (current_user.id != order.customer_id and 
        current_user.id != order.driver_id and 
        current_user.role != "admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return order
