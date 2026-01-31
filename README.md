# DOT Platform Backend

Backend API for DOT ride-hailing and delivery platform built with FastAPI and PostgreSQL.

## Features

- User authentication (JWT)
- Driver wallet system with configurable commission
- Taxi ride booking
- Delivery service with smart recipient location
- Real-time tracking via WebSockets
- Google Maps integration
- Comprehensive admin dashboard APIs
- Complete order logging for dispute resolution

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and update the values:

```bash
cp .env.example .env
```

Update these values in `.env`:
- `DATABASE_URL`: Your PostgreSQL connection string
- `SECRET_KEY`: Generate a secure secret key
- `GOOGLE_MAPS_API_KEY`: Already configured

### 3. Setup PostgreSQL

```bash
# Create database
createdb dot_db

# Or using psql
psql -U postgres
CREATE DATABASE dot_db;
CREATE USER dot_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE dot_db TO dot_user;
\q
```

### 4. Run the Server

```bash
# Development mode with auto-reload
uvicorn app.main:app --reload

# Or using Python
python -m app.main
```

The API will be available at: `http://localhost:8000`

API Documentation: `http://localhost:8000/docs`

## API Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login and get token

### Orders
- `POST /orders/taxi` - Create taxi ride
- `POST /orders/delivery` - Create delivery
- `GET /orders/pending` - Get pending orders (drivers)
- `POST /orders/accept` - Accept order (driver)
- `POST /orders/update-status` - Update order status
- `POST /orders/cancel` - Cancel order
- `GET /orders/my-orders` - Get user's orders

### Driver
- `GET /driver/wallet` - Get wallet info
- `GET /driver/transactions` - Get transaction history
- `GET /driver/can-accept-orders` - Check balance status

### Admin
- `GET /admin/users` - List all users
- `POST /admin/users/{id}/toggle-active` - Activate/deactivate user
- `POST /admin/wallet/top-up` - Top up driver wallet
- `GET /admin/drivers/stats` - Get driver statistics
- `GET /admin/orders/logs` - Get order logs
- `GET /admin/orders/{id}/status-history` - Get order status history
- `GET /admin/settings` - Get platform settings
- `POST /admin/settings` - Update settings
- `GET /admin/dashboard/stats` - Get dashboard statistics

### Ratings
- `POST /ratings/` - Create rating
- `GET /ratings/driver/{id}` - Get driver ratings
- `GET /ratings/my-ratings` - Get my ratings

### WebSocket
- `WS /ws/{user_id}` - WebSocket connection for real-time updates

## WebSocket Message Types

### Driver Location Update
```json
{
  "type": "driver_location",
  "data": {
    "latitude": 36.2021,
    "longitude": 37.1343
  }
}
```

### Order Update
```json
{
  "type": "order_update",
  "data": {
    "order_id": 123,
    "status": "accepted",
    "customer_id": 456
  }
}
```

### New Order
```json
{
  "type": "new_order",
  "data": {
    "order_id": 123,
    "order_type": "taxi"
  }
}
```

## Default Commission

Default commission is set to 5000 SYP per order. This can be changed in:
1. `.env` file: `DEFAULT_COMMISSION=5000`
2. Through admin API: `POST /admin/settings`

## Testing

Create a test admin user:

```python
# Run Python in the backend directory
python

# Then execute:
from app.database import AsyncSessionLocal
from app.models import User, UserRole
from app.auth import get_password_hash
import asyncio

async def create_admin():
    async with AsyncSessionLocal() as db:
        admin = User(
            phone="0999999999",
            name="Admin",
            role=UserRole.ADMIN,
            password_hash=get_password_hash("admin123")
        )
        db.add(admin)
        await db.commit()
        print("Admin created successfully!")

asyncio.run(create_admin())
```

## Production Deployment

1. Set proper `SECRET_KEY` in production
2. Update CORS origins in `main.py`
3. Use production PostgreSQL database
4. Configure SMS provider credentials
5. Optionally add Firebase for push notifications
6. Use HTTPS for WebSocket connections (wss://)
