from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import List
from datetime import datetime, timedelta
from ..database import get_db
from ..models import User, Order, Wallet, Transaction, Settings as SettingsModel, OrderStatusLog, Rating, UserRole, OrderStatus
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
        # جميع المستخدمين
        total_users_result = await db.execute(
            select(func.count(User.id))
        )
        total_users = total_users_result.scalar() or 0
        
        # السائقين النشطين
        total_drivers_result = await db.execute(
            select(func.count(User.id)).filter(
                and_(
                    User.role == UserRole.DRIVER,
                    User.is_active == True
                )
            )
        )
        total_drivers = total_drivers_result.scalar() or 0
        
        # جميع الطلبات
        today_orders_result = await db.execute(
            select(func.count(Order.id))
        )
        today_orders = today_orders_result.scalar() or 0
        
        # إجمالي الأرباح
        total_revenue_result = await db.execute(
            select(func.sum(Order.final_price)).filter(
                Order.status == OrderStatus.COMPLETED
            )
        )
        total_revenue = total_revenue_result.scalar() or 0
        
        return {
            "total_users": total_users,
            "total_drivers": total_drivers,
            "today_orders": today_orders,
            "total_revenue": int(total_revenue)
        }
    except Exception as e:
        # Return fallback data instead of 500 error
        return {
            "total_users": 0,
            "total_drivers": 0,
            "today_orders": 0,
            "total_revenue": 0
        }


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
    users = result.scalars().all()
    
    # Convert to UserResponse format with full_name alias
    response_users = []
    for user in users:
        user_dict = {
            "id": user.id,
            "phone": user.phone,
            "email": user.email,
            "name": user.name,
            "full_name": user.name,  # Add full_name alias
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at
        }
        response_users.append(user_dict)
    
    return response_users


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


@router.patch("/users/{user_id}/status")
async def patch_user_status(
    user_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Patch endpoint for user status (alias for toggle)"""
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


@router.get("/drivers")
async def get_all_drivers(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all drivers with full details"""
    result = await db.execute(
        select(User).filter(User.role == UserRole.DRIVER).order_by(User.created_at.desc())
    )
    drivers = result.scalars().all()
    
    # Get average rating for each driver
    driver_list = []
    for driver in drivers:
        avg_rating_result = await db.execute(
            select(func.avg(Rating.rating)).filter(Rating.driver_id == driver.id)
        )
        avg_rating = avg_rating_result.scalar() or 0.0
        
        driver_dict = {
            "id": driver.id,
            "phone": driver.phone,
            "email": driver.email,
            "name": driver.name,
            "full_name": driver.name,  # Add full_name alias
            "role": driver.role.value,
            "is_active": driver.is_active,
            "rating": round(float(avg_rating), 1),
            "created_at": driver.created_at
        }
        driver_list.append(driver_dict)
    
    return driver_list


@router.patch("/drivers/{driver_id}/status")
async def patch_driver_status(
    driver_id: int,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Patch endpoint for driver status"""
    result = await db.execute(select(User).filter(User.id == driver_id))
    driver = result.scalar_one_or_none()
    
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    driver.is_active = not driver.is_active
    await db.commit()
    
    return {
        "status": "success",
        "driver_id": driver_id,
        "is_active": driver.is_active
    }


@router.get("/orders")
async def get_all_orders(
    status: str = None,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all orders with complete details"""
    query = select(Order).order_by(Order.created_at.desc())
    
    if status:
        query = query.filter(Order.status == status)
    
    result = await db.execute(query)
    orders = result.scalars().all()
    
    # Convert to proper response format
    order_list = []
    for order in orders:
        order_dict = {
            "id": order.id,
            "order_type": order.type.value if hasattr(order.type, 'value') else order.type,
            "status": order.status.value if hasattr(order.status, 'value') else order.status,
            "customer_id": order.customer_id,
            "driver_id": order.driver_id,
            "price": order.final_price or order.estimated_price or 0,
            "final_price": order.final_price,
            "estimated_price": order.estimated_price,
            "pickup_location": order.pickup_address or f"{order.pickup_lat},{order.pickup_lng}",
            "destination_location": order.dropoff_address or f"{order.dropoff_lat},{order.dropoff_lng}",
            "created_at": order.created_at
        }
        order_list.append(order_dict)
    
    return order_list


@router.get("/pricing")
async def get_pricing_config(
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get current pricing configuration from database or defaults"""
    
    # Try to get pricing from database first
    try:
        result_taxi_base = await db.execute(
            select(SettingsModel).filter(SettingsModel.key == "taxi_base_price")
        )
        setting_taxi_base = result_taxi_base.scalar_one_or_none()
        
        result_taxi_km = await db.execute(
            select(SettingsModel).filter(SettingsModel.key == "taxi_price_per_km")
        )
        setting_taxi_km = result_taxi_km.scalar_one_or_none()
        
        result_delivery_base = await db.execute(
            select(SettingsModel).filter(SettingsModel.key == "delivery_base_price")
        )
        setting_delivery_base = result_delivery_base.scalar_one_or_none()
        
        result_delivery_km = await db.execute(
            select(SettingsModel).filter(SettingsModel.key == "delivery_price_per_km")
        )
        setting_delivery_km = result_delivery_km.scalar_one_or_none()
        
        return {
            "taxi_base_price": float(setting_taxi_base.value) if setting_taxi_base else settings.TAXI_BASE_PRICE,
            "taxi_price_per_km": float(setting_taxi_km.value) if setting_taxi_km else settings.TAXI_PRICE_PER_KM,
            "delivery_base_price": float(setting_delivery_base.value) if setting_delivery_base else settings.DELIVERY_BASE_PRICE,
            "delivery_price_per_km": float(setting_delivery_km.value) if setting_delivery_km else settings.DELIVERY_PRICE_PER_KM
        }
    except Exception as e:
        # Return defaults if there's an error
        return {
            "taxi_base_price": settings.TAXI_BASE_PRICE,
            "taxi_price_per_km": settings.TAXI_PRICE_PER_KM,
            "delivery_base_price": settings.DELIVERY_BASE_PRICE,
            "delivery_price_per_km": settings.DELIVERY_PRICE_PER_KM
        }


@router.put("/pricing")
async def update_pricing_config(
    pricing_data: dict,
    current_admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update pricing configuration and save to database"""
    
    try:
        # Keys mapping
        keys_to_update = [
            "taxi_base_price",
            "taxi_price_per_km",
            "delivery_base_price",
            "delivery_price_per_km"
        ]
        
        # Update or create settings for each pricing field
        for key in keys_to_update:
            if key in pricing_data:
                value = pricing_data[key]
                
                result = await db.execute(
                    select(SettingsModel).filter(SettingsModel.key == key)
                )
                setting = result.scalar_one_or_none()
                
                if setting:
                    setting.value = str(value)
                    setting.updated_at = datetime.utcnow()
                else:
                    # Create new setting
                    new_setting = SettingsModel(
                        key=key,
                        value=str(value),
                        description=f"Pricing configuration: {key}"
                    )
                    db.add(new_setting)
        
        # Commit all changes
        await db.commit()
        
        # Return updated values
        return {
            "status": "success",
            "message": "تم تحديث الأسعار بنجاح",
            "taxi_base_price": float(pricing_data.get("taxi_base_price", 5000)),
            "taxi_price_per_km": float(pricing_data.get("taxi_price_per_km", 5000)),
            "delivery_base_price": float(pricing_data.get("delivery_base_price", 3000)),
            "delivery_price_per_km": float(pricing_data.get("delivery_price_per_km", 2500))
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating pricing: {str(e)}")


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



