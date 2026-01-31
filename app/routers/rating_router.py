from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List
from ..database import get_db
from ..models import Rating, Order, User, OrderStatus
from ..schemas import RatingCreate, RatingResponse
from ..auth import get_current_user

router = APIRouter(prefix="/ratings", tags=["ratings"])


@router.post("/", response_model=RatingResponse, status_code=status.HTTP_201_CREATED)
async def create_rating(
    rating_data: RatingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a rating for a completed order"""
    
    # Get order
    result = await db.execute(
        select(Order).filter(Order.id == rating_data.order_id)
    )
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Verify user is the customer
    if order.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Verify order is completed
    if order.status != OrderStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only rate completed orders"
        )
    
    # Check if already rated
    existing_rating = await db.execute(
        select(Rating).filter(Rating.order_id == rating_data.order_id)
    )
    if existing_rating.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order already rated"
        )
    
    # Create rating
    new_rating = Rating(
        order_id=rating_data.order_id,
        customer_id=current_user.id,
        driver_id=order.driver_id,
        rating=rating_data.rating,
        comment=rating_data.comment
    )
    
    db.add(new_rating)
    await db.commit()
    await db.refresh(new_rating)
    
    return new_rating


@router.get("/driver/{driver_id}", response_model=List[RatingResponse])
async def get_driver_ratings(
    driver_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get all ratings for a specific driver"""
    
    result = await db.execute(
        select(Rating)
        .filter(Rating.driver_id == driver_id)
        .order_by(Rating.created_at.desc())
    )
    
    return result.scalars().all()


@router.get("/my-ratings", response_model=List[RatingResponse])
async def get_my_ratings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get ratings given by current user or received if driver"""
    
    if current_user.role == "driver":
        result = await db.execute(
            select(Rating)
            .filter(Rating.driver_id == current_user.id)
            .order_by(Rating.created_at.desc())
        )
    else:
        result = await db.execute(
            select(Rating)
            .filter(Rating.customer_id == current_user.id)
            .order_by(Rating.created_at.desc())
        )
    
    return result.scalars().all()
