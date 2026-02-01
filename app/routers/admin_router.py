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


@router.get("/stats")
async def get_dashboard_stats(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard statistics from real data"""
    try:
        # عدد المستخدمين (بدون admin)
        total_users_query = select(func.count(User.id)).where(
            User.role.astext != UserRole.ADMIN.value
        )
        total_users_result = await db.execute(total_users_query)
        total_users = total_users_result.scalar() or 0
        
        # عدد السائقين النشطين
        total_drivers_query = select(func.count(User.id)).where(
            and_(
                User.role.astext == UserRole.DRIVER.value,
                User.is_active == True
            )
        )
        total_drivers_result = await db.execute(total_drivers_query)
        total_drivers = total_drivers_result.scalar() or 0
        
        # عدد الطلبات اليوم
        today = datetime.now().date()
        today_orders_query = select(func.count(Order.id)).where(
            and_(
                Order.created_at >= datetime.combine(today, datetime.min.time()),
                Order.created_at <= datetime.combine(today, datetime.max.time())
            )
        )
        today_orders_result = await db.execute(today_orders_query)
        today_orders = today_orders_result.scalar() or 0
        
        # إجمالي الأرباح اليوم (الطلبات المكتملة فقط)
        today_revenue_query = select(func.sum(Order.price)).where(
            and_(
                Order.created_at >= datetime.combine(today, datetime.min.time()),
                Order.created_at <= datetime.combine(today, datetime.max.time()),
                Order.status == "completed"
            )
        )
        today_revenue_result = await db.execute(today_revenue_query)
        today_revenue = today_revenue_result.scalar() or 0
        
        return {
            "total_users": total_users,
            "total_drivers": total_drivers,
            "today_orders": today_orders,
            "total_revenue": int(today_revenue)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/setup-admin/{user_id}")
async def setup_admin_user(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Setup admin role for a user (one-time setup endpoint)"""
    try:
        result = await db.execute(
            select(User).filter(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.role = UserRole.ADMIN
        await db.commit()
        await db.refresh(user)
        
        return {
            "message": f"User {user_id} has been set as admin",
            "user_id": user.id,
            "role": user.role.value,
            "name": user.name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/init-admin")
async def init_admin(db: AsyncSession = Depends(get_db)):
    """Initialize admin user with default credentials"""
    from ..auth import get_password_hash
    
    try:
        phone = "0912345678"
        password = "Admin091234567"
        name = "Admin"
        email = "admin@dot.com"
        
        # Check if admin already exists
        result = await db.execute(
            select(User).filter(User.phone == phone)
        )
        admin_user = result.scalar_one_or_none()
        
        if admin_user:
            # Update existing user to admin
            admin_user.role = UserRole.ADMIN
            await db.commit()
            await db.refresh(admin_user)
            return {
                "message": "Admin user already exists - updated to admin role",
                "phone": admin_user.phone,
                "role": admin_user.role.value
            }
        else:
            # Create new admin user
            hashed_password = get_password_hash(password)
            new_admin = User(
                phone=phone,
                email=email,
                name=name,
                role=UserRole.ADMIN,
                password_hash=hashed_password
            )
            db.add(new_admin)
            await db.commit()
            await db.refresh(new_admin)
            
            return {
                "message": "Admin user created successfully",
                "phone": new_admin.phone,
                "name": new_admin.name,
                "role": new_admin.role.value
            }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


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
async def get_admin_dashboard_stats(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get overview statistics for admin dashboard (DEPRECATED - use /admin/stats instead)"""
    # عدد المستخدمين (بدون admin)
    total_users_result = await db.execute(
        select(func.count(User.id)).where(
            User.role.astext != UserRole.ADMIN.value
        )
    )
    total_users = total_users_result.scalar() or 0
    
    # عدد السائقين النشطين
    total_drivers_result = await db.execute(
        select(func.count(User.id)).where(
            and_(
                User.role.astext == UserRole.DRIVER.value,
                User.is_active == True
            )
        )
    )
    total_drivers = total_drivers_result.scalar() or 0
    
    # عدد الطلبات اليوم
    today = datetime.now().date()
    today_orders_result = await db.execute(
        select(func.count(Order.id)).where(
            and_(
                Order.created_at >= datetime.combine(today, datetime.min.time()),
                Order.created_at <= datetime.combine(today, datetime.max.time())
            )
        )
    )
    today_orders = today_orders_result.scalar() or 0
    
    # إجمالي الأرباح اليوم
    today_revenue_result = await db.execute(
        select(func.sum(Order.price)).where(
            and_(
                Order.created_at >= datetime.combine(today, datetime.min.time()),
                Order.created_at <= datetime.combine(today, datetime.max.time()),
                Order.status == "completed"
            )
        )
    )
    today_revenue = today_revenue_result.scalar() or 0
    
    return {
        "total_users": total_users,
        "total_drivers": total_drivers,
        "orders_today": today_orders,
        "total_revenue": int(today_revenue)
    }
