from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path
from .database import engine, Base
from .routers import (
    auth_router,
    orders_router,
    driver_router,
    admin_router,
    rating_router,
    websocket_router,
    files_router
)

# Updated: Added admin stats endpoint for real dashboard data (Feb 1, 2026)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown: Close database connections
    await engine.dispose()


app = FastAPI(
    title="DOT Platform API",
    description="Backend API for DOT ride-hailing and delivery platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router.router)
app.include_router(orders_router.router)
app.include_router(driver_router.router)
app.include_router(admin_router.router)
app.include_router(rating_router.router)
app.include_router(websocket_router.router)
app.include_router(files_router.router)

# Mount static files for uploads
uploads_path = Path("uploads")
uploads_path.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get("/")
async def root():
    return {
        "message": "DOT Platform API",
        "version": "1.0.0",
        "status": "active"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
