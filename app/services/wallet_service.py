from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from ..models import Wallet, Transaction, TransactionType, User
from ..config import settings
from typing import Optional


class WalletService:
    """Wallet management and transaction processing"""
    
    @staticmethod
    async def get_or_create_wallet(db: AsyncSession, user_id: int) -> Wallet:
        """Get existing wallet or create new one"""
        result = await db.execute(
            select(Wallet).filter(Wallet.user_id == user_id)
        )
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            wallet = Wallet(user_id=user_id, balance=0.0)
            db.add(wallet)
            await db.commit()
            await db.refresh(wallet)
        
        return wallet
    
    @staticmethod
    async def top_up(
        db: AsyncSession,
        driver_id: int,
        amount: float,
        admin_id: int
    ) -> Transaction:
        """Add money to driver's wallet"""
        wallet = await WalletService.get_or_create_wallet(db, driver_id)
        
        # Update balance
        wallet.balance += amount
        
        # Create transaction record
        transaction = Transaction(
            wallet_id=wallet.id,
            type=TransactionType.TOP_UP,
            amount=amount,
            description=f"Wallet top-up by admin #{admin_id}",
            admin_id=admin_id
        )
        
        db.add(transaction)
        await db.commit()
        await db.refresh(transaction)
        
        return transaction
    
    @staticmethod
    async def deduct_commission(
        db: AsyncSession,
        driver_id: int,
        order_id: int,
        commission_amount: Optional[float] = None
    ) -> Optional[Transaction]:
        """Deduct commission from driver's wallet after order completion"""
        wallet = await WalletService.get_or_create_wallet(db, driver_id)
        
        # Use default commission if not specified
        if commission_amount is None:
            commission_amount = settings.DEFAULT_COMMISSION
        
        # Check if wallet has sufficient balance
        if wallet.balance < commission_amount:
            return None
        
        # Deduct from balance
        wallet.balance -= commission_amount
        
        # Create transaction record
        transaction = Transaction(
            wallet_id=wallet.id,
            type=TransactionType.DEDUCTION,
            amount=commission_amount,
            description=f"Commission for order #{order_id}",
            order_id=order_id
        )
        
        db.add(transaction)
        await db.commit()
        await db.refresh(transaction)
        
        return transaction
    
    @staticmethod
    async def can_accept_orders(db: AsyncSession, driver_id: int) -> bool:
        """Check if driver has sufficient balance to accept orders"""
        wallet = await WalletService.get_or_create_wallet(db, driver_id)
        return wallet.balance >= settings.DEFAULT_COMMISSION
    
    @staticmethod
    async def get_balance(db: AsyncSession, user_id: int) -> float:
        """Get current wallet balance"""
        wallet = await WalletService.get_or_create_wallet(db, user_id)
        return wallet.balance
    
    @staticmethod
    async def get_transactions(
        db: AsyncSession,
        user_id: int,
        limit: int = 50
    ) -> list[Transaction]:
        """Get transaction history"""
        wallet = await WalletService.get_or_create_wallet(db, user_id)
        
        result = await db.execute(
            select(Transaction)
            .filter(Transaction.wallet_id == wallet.id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
        )
        
        return result.scalars().all()


wallet_service = WalletService()
