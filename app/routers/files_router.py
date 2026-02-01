from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import aiofiles
import os
from pathlib import Path
from datetime import datetime
from ..database import get_db
from ..auth import get_current_user
from ..models import User

router = APIRouter(prefix="/files", tags=["file-upload"])

# Create uploads directory
UPLOAD_DIR = Path("uploads")
try:
    UPLOAD_DIR.mkdir(exist_ok=True)
except Exception as e:
    print(f"Warning: Could not create uploads directory: {e}")


@router.post("/upload-id-photo")
async def upload_id_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload ID photo for driver verification"""
    
    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="صيغة الصورة غير صحيحة. استخدم JPEG أو PNG"
        )
    
    # Validate file size (max 5MB)
    file_size = await file.read()
    if len(file_size) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="حجم الملف كبير جداً (الحد الأقصى 5MB)"
        )
    await file.seek(0)
    
    try:
        # Create filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = file.filename.split(".")[-1]
        filename = f"id_photo_{current_user.id}_{timestamp}.{file_extension}"
        filepath = UPLOAD_DIR / filename
        
        # Save file
        async with aiofiles.open(filepath, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Return URL for storage
        file_url = f"/uploads/{filename}"
        
        return {
            "status": "success",
            "filename": filename,
            "url": file_url,
            "message": "تم تحميل صورة الهوية بنجاح"
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطأ في تحميل الملف: {str(e)}"
        )


@router.post("/upload-photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload profile photo"""
    
    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="صيغة الصورة غير صحيحة. استخدم JPEG أو PNG"
        )
    
    # Validate file size (max 3MB)
    file_size = await file.read()
    if len(file_size) > 3 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="حجم الملف كبير جداً (الحد الأقصى 3MB)"
        )
    await file.seek(0)
    
    try:
        # Create filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = file.filename.split(".")[-1]
        filename = f"profile_{current_user.id}_{timestamp}.{file_extension}"
        filepath = UPLOAD_DIR / filename
        
        # Save file
        async with aiofiles.open(filepath, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Return URL for storage
        file_url = f"/uploads/{filename}"
        
        return {
            "status": "success",
            "filename": filename,
            "url": file_url,
            "message": "تم تحميل الصورة بنجاح"
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطأ في تحميل الملف: {str(e)}"
        )
