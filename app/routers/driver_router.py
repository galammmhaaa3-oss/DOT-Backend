from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from ..database import get_db
from ..models import User
from ..schemas import (
    WalletResponse,
    TransactionResponse,
    LocationUpdate
)
from ..auth import get_current_driver
from ..services.wallet_service import wallet_service

router = APIRouter(prefix="/driver", tags=["driver"])


@router.get("/wallet", response_model=WalletResponse)
async def get_wallet(
    current_driver: User = Depends(get_current_driver),
    db: AsyncSession = Depends(get_db)
):
    """Get driver's wallet information"""
    wallet = await wallet_service.get_or_create_wallet(db, current_driver.id)
    return wallet


@router.get("/transactions", response_model=List[TransactionResponse])
async def get_transactions(
    limit: int = 50,
    current_driver: User = Depends(get_current_driver),
    db: AsyncSession = Depends(get_db)
):
    """Get driver's transaction history"""
    transactions = await wallet_service.get_transactions(db, current_driver.id, limit)
    return transactions


@router.get("/can-accept-orders")
async def can_accept_orders(
    current_driver: User = Depends(get_current_driver),
    db: AsyncSession = Depends(get_db)
):
    """Check if driver has sufficient balance to accept orders"""
    can_accept = await wallet_service.can_accept_orders(db, current_driver.id)
    balance = await wallet_service.get_balance(db, current_driver.id)
    
    return {
        "can_accept": can_accept,
        "balance": balance,
        "message": "Sufficient balance" if can_accept else "Please top up your wallet"
    }


@router.post("/location")
async def update_location(
    location: LocationUpdate,
    current_driver: User = Depends(get_current_driver)
):
    """Update driver's current location (for real-time tracking)"""
    # This will be handled by WebSocket in production
    # This endpoint is for fallback/testing
    return {
        "status": "success",
        "message": "Location updated",
        "driver_id": current_driver.id
    }
