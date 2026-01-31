from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import List
from datetime import datetime, timedelta
from ..database import get_db
from ..models import User, Order, Wallet, Transaction, Settings as SettingsModel, OrderStatusLog, Rating, UserRole
from ..schemas import (
    UserResponse,
    WalletTopUp,
    SettingUpdate,
    SettingResponse,
    DriverStats,
    OrderLog,
    OrderResponse
)
from ..auth import get_current_admin
from ..services.wallet_service import wallet_service
from ..config import settings

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    role: str = None,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all users with optional role filter"""
    query = select(User)
    
    if role:
        query = query.filter(User.role == role)
    
    result = await db.execute(query.order_by(User.created_at.desc()))
    return result.scalars().all()


@router.post("/users/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Activate or deactivate a user"""
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = not user.is_active
    await db.commit()
    
    return {
        "status": "success",
        "user_id": user_id,
        "is_active": user.is_active
    }


@router.post("/wallet/top-up")
async def top_up_wallet(
    top_up_data: WalletTopUp,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Manually top up a driver's wallet when they pay cash"""
    
    # Verify driver exists
    result = await db.execute(
        select(User).filter(
            and_(
                User.id == top_up_data.driver_id,
                User.role == UserRole.DRIVER
            )
        )
    )
    driver = result.scalar_one_or_none()
    
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    # Process top-up
    transaction = await wallet_service.top_up(
        db,
        top_up_data.driver_id,
        top_up_data.amount,
        current_admin.id
    )
    
    return {
        "status": "success",
        "transaction_id": transaction.id,
        "driver_id": top_up_data.driver_id,
        "amount": top_up_data.amount
    }


@router.get("/drivers/stats", response_model=List[DriverStats])
async def get_driver_stats(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get statistics for all drivers"""
    
    # Get all drivers
    drivers_result = await db.execute(
        select(User).filter(User.role == UserRole.DRIVER)
    )
    drivers = drivers_result.scalars().all()
    
    stats_list = []
    
    for driver in drivers:
        # Count orders
        total_orders_result = await db.execute(
            select(func.count(Order.id)).filter(Order.driver_id == driver.id)
        )
        total_orders = total_orders_result.scalar() or 0
        
        completed_orders_result = await db.execute(
            select(func.count(Order.id)).filter(
                and_(
                    Order.driver_id == driver.id,
                    Order.status == "completed"
                )
            )
        )
        completed_orders = completed_orders_result.scalar() or 0
        
        cancelled_orders_result = await db.execute(
            select(func.count(Order.id)).filter(
                and_(
                    Order.driver_id == driver.id,
                    Order.status == "cancelled"
                )
            )
        )
        cancelled_orders = cancelled_orders_result.scalar() or 0
        
        # Average rating
        avg_rating_result = await db.execute(
            select(func.avg(Rating.rating)).filter(Rating.driver_id == driver.id)
        )
        avg_rating = avg_rating_result.scalar() or 0.0
        
        # Wallet balance
        balance = await wallet_service.get_balance(db, driver.id)
        
        stats_list.append(DriverStats(
            driver_id=driver.id,
            driver_name=driver.name,
            total_orders=total_orders,
            completed_orders=completed_orders,
            cancelled_orders=cancelled_orders,
            average_rating=round(avg_rating, 2),
            wallet_balance=balance
        ))
    
    return stats_list


@router.get("/orders/logs", response_model=List[OrderResponse])
async def get_order_logs(
    days: int = 7,
    status: str = None,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed order logs for dispute resolution"""
    
    # Calculate date range
    start_date = datetime.utcnow() - timedelta(days=days)
    
    query = select(Order).filter(Order.created_at >= start_date)
    
    if status:
        query = query.filter(Order.status == status)
    
    result = await db.execute(query.order_by(Order.created_at.desc()))
    return result.scalars().all()


@router.get("/orders/{order_id}/status-history")
async def get_order_status_history(
    order_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get complete status change history for an order (for dispute resolution)"""
    
    result = await db.execute(
        select(OrderStatusLog)
        .filter(OrderStatusLog.order_id == order_id)
        .order_by(OrderStatusLog.timestamp.asc())
    )
    logs = result.scalars().all()
    
    return [
        {
            "id": log.id,
            "old_status": log.old_status,
            "new_status": log.new_status,
            "changed_by": log.changed_by,
            "timestamp": log.timestamp,
            "notes": log.notes
        }
        for log in logs
    ]


@router.get("/settings", response_model=List[SettingResponse])
async def get_settings(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all platform settings"""
    result = await db.execute(select(SettingsModel))
    return result.scalars().all()


@router.post("/settings", response_model=SettingResponse)
async def update_setting(
    setting_data: SettingUpdate,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update a platform setting (e.g., commission rate)"""
    
    result = await db.execute(
        select(SettingsModel).filter(SettingsModel.key == setting_data.key)
    )
    setting = result.scalar_one_or_none()
    
    if setting:
        setting.value = setting_data.value
    else:
        setting = SettingsModel(
            key=setting_data.key,
            value=setting_data.value
        )
        db.add(setting)
    
    await db.commit()
    await db.refresh(setting)
    
    return setting


@router.get("/dashboard/stats")
async def get_dashboard_stats(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get overview statistics for admin dashboard"""
    
    # Total users
    total_users = await db.execute(
        select(func.count(User.id)).filter(User.role == UserRole.CUSTOMER)
    )
    
    # Total drivers
    total_drivers = await db.execute(
        select(func.count(User.id)).filter(User.role == UserRole.DRIVER)
    )
    
    # Active drivers (with balance)
    active_drivers = await db.execute(
        select(func.count(Wallet.id)).filter(Wallet.balance >= settings.DEFAULT_COMMISSION)
    )
    
    # Orders today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    orders_today = await db.execute(
        select(func.count(Order.id)).filter(Order.created_at >= today_start)
    )
    
    # Revenue (total commissions) - from completed orders
    total_revenue = await db.execute(
        select(func.sum(Transaction.amount)).filter(
            Transaction.type == "deduction"
        )
    )
    
    return {
        "total_users": total_users.scalar() or 0,
        "total_drivers": total_drivers.scalar() or 0,
        "active_drivers": active_drivers.scalar() or 0,
        "orders_today": orders_today.scalar() or 0,
        "total_revenue": total_revenue.scalar() or 0
    }
