from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta, datetime
from pydantic import BaseModel
from ..database import get_db
from ..models import User, Wallet, UserRole
from ..schemas import UserCreate, UserLogin, Token, UserResponse, UserAuthResponse
from ..auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user
)
from ..config import settings

router = APIRouter(prefix="/auth", tags=["authentication"])


# Schema for change password
class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.post("/register", response_model=UserAuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    phone: str = Form(...),
    email: str = Form(...),
    name: str = Form(...),
    password: str = Form(...),
    role: str = Form(default="customer"),
    id_name: str = Form(None),
    national_id: str = Form(None),
    birth_date: str = Form(None),
    id_photo: UploadFile = File(None),
    db: AsyncSession = Depends(get_db)
):
    """Register a new user (customer, driver, or admin)"""
    
    try:
        # Check if user already exists
        result = await db.execute(
            select(User).filter(User.phone == phone)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered"
            )
        
        # Check if national ID already exists (for drivers)
        if national_id:
            result = await db.execute(
                select(User).filter(User.national_id == national_id)
            )
            existing_id = result.scalar_one_or_none()
            if existing_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="National ID already registered"
                )
        
        # Parse birth_date if provided
        birth_date_obj = None
        if birth_date:
            try:
                birth_date_obj = datetime.fromisoformat(birth_date.replace('Z', '+00:00'))
            except:
                birth_date_obj = None
        
        # Parse role
        user_role = UserRole.CUSTOMER
        try:
            user_role = UserRole(role)
        except:
            user_role = UserRole.CUSTOMER
        
        # Handle id_photo_url (just store filename reference for now)
        id_photo_url = None
        if id_photo and id_photo.filename:
            # Will be populated after user creation
            id_photo_url = None
        
        # Create new user
        hashed_password = get_password_hash(password)
        new_user = User(
            phone=phone,
            email=email,
            name=name,
            role=user_role,
            password_hash=hashed_password,
            id_name=id_name if id_name else None,
            national_id=national_id if national_id else None,
            id_photo_url=id_photo_url,
            birth_date=birth_date_obj
        )
        
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        # If id_photo provided, save it
        if id_photo and id_photo.filename:
            try:
                from pathlib import Path
                import aiofiles
                
                # Create uploads directory
                upload_dir = Path("uploads")
                upload_dir.mkdir(exist_ok=True)
                
                # Create unique filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_extension = id_photo.filename.split(".")[-1]
                filename = f"id_photo_{new_user.id}_{timestamp}.{file_extension}"
                file_path = upload_dir / filename
                
                # Save file
                contents = await id_photo.read()
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(contents)
                
                # Update user with photo URL
                new_user.id_photo_url = f"/uploads/{filename}"
                await db.commit()
                await db.refresh(new_user)
            except Exception as e:
                print(f"Error saving ID photo: {e}")
                # Don't fail registration if photo fails
        
        # Create wallet for drivers
        if new_user.role == UserRole.DRIVER:
            wallet = Wallet(user_id=new_user.id, balance=0.0)
            db.add(wallet)
            await db.commit()
        
        # Create token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(new_user.id), "role": new_user.role.value},
            expires_delta=access_token_expires
        )
        
        # Return user with token
        return {
            "id": new_user.id,
            "phone": new_user.phone,
            "email": new_user.email,
            "name": new_user.name,
            "role": new_user.role.value,
            "is_active": new_user.is_active,
            "created_at": new_user.created_at,
            "id_name": new_user.id_name,
            "national_id": new_user.national_id,
            "id_photo_url": new_user.id_photo_url,
            "birth_date": new_user.birth_date,
            "access_token": access_token
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration error: {str(e)}"
        )


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login and get access token"""
    
    # Find user
    result = await db.execute(
        select(User).filter(User.phone == credentials.phone)
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect phone or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is inactive"
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user profile information"""
    return current_user


@router.post("/me/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change user password"""
    
    # Verify old password
    if not verify_password(request.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="كلمة المرور القديمة غير صحيحة"
        )
    
    # Validate new password
    if len(request.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="كلمة المرور الجديدة يجب أن تكون 6 أحرف على الأقل"
        )
    
    # Update password
    current_user.password_hash = get_password_hash(request.new_password)
    await db.commit()
    
    return {
        "status": "success",
        "message": "تم تغيير كلمة المرور بنجاح"
    }

