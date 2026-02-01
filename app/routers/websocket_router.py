from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Dict, Set
import json
from datetime import datetime
from ..auth import get_current_user
from ..models import User

router = APIRouter()

# Store active WebSocket connections
class ConnectionManager:
    def __init__(self):
        # Active connections by user_id
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # Driver locations: driver_id -> {lat, lng, timestamp}
        self.driver_locations: Dict[int, dict] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
    
    async def send_to_user(self, user_id: int, message: dict):
        """Send message to all connections of a specific user"""
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass
    
    async def broadcast_to_drivers(self, message: dict):
        """Broadcast message to all connected drivers"""
        for user_id, connections in self.active_connections.items():
            for connection in connections:
                try:
                    await connection.send_json(message)
                except:
                    pass
    
    async def broadcast_to_admins(self, message: dict):
        """Broadcast message to all connected admins"""
        # In production, track admin connections separately
        for user_id, connections in self.active_connections.items():
            for connection in connections:
                try:
                    await connection.send_json(message)
                except:
                    pass
    
    def update_driver_location(self, driver_id: int, lat: float, lng: float):
        """Update driver's current location"""
        self.driver_locations[driver_id] = {
            "latitude": lat,
            "longitude": lng,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_all_driver_locations(self) -> dict:
        """Get all active driver locations"""
        return self.driver_locations


manager = ConnectionManager()


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    """
    WebSocket endpoint for real-time updates
    
    Messages format:
    {
        "type": "driver_location" | "order_update" | "new_order",
        "data": {...}
    }
    """
    await manager.connect(websocket, user_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            message_type = message.get("type")
            message_data = message.get("data", {})
            
            if message_type == "driver_location":
                # Driver updating their location
                lat = message_data.get("latitude")
                lng = message_data.get("longitude")
                
                if lat and lng:
                    manager.update_driver_location(user_id, lat, lng)
                    
                    # Broadcast to admin dashboard
                    await manager.broadcast_to_admins({
                        "type": "driver_location",
                        "data": {
                            "driver_id": user_id,
                            "latitude": lat,
                            "longitude": lng,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    })
            
            elif message_type == "order_update":
                # Order status update - notify customer
                customer_id = message_data.get("customer_id")
                if customer_id:
                    await manager.send_to_user(customer_id, {
                        "type": "order_update",
                        "data": message_data
                    })
                
                # Also broadcast to admin
                await manager.broadcast_to_admins({
                    "type": "order_update",
                    "data": message_data
                })
            
            elif message_type == "new_order":
                # New order created - notify all drivers
                await manager.broadcast_to_drivers({
                    "type": "new_order",
                    "data": message_data
                })
                
                # Notify admin
                await manager.broadcast_to_admins({
                    "type": "new_order",
                    "data": message_data
                })
            
            elif message_type == "get_driver_locations":
                # Admin requesting all driver locations
                locations = manager.get_all_driver_locations()
                await websocket.send_json({
                    "type": "driver_locations",
                    "data": locations
                })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket, user_id)


# Helper function to broadcast order updates from API routes
async def broadcast_order_update(order_id: int, status: str, customer_id: int, driver_id: int = None):
    """Broadcast order update to relevant parties"""
    message = {
        "type": "order_update",
        "data": {
            "order_id": order_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    
    # Notify customer
    await manager.send_to_user(customer_id, message)
    
    # Notify driver if assigned
    if driver_id:
        await manager.send_to_user(driver_id, message)
    
    # Notify admin
    await manager.broadcast_to_admins(message)


async def broadcast_new_order(order_id: int, order_type: str):
    """Broadcast new order to all drivers"""
    message = {
        "type": "new_order",
        "data": {
            "order_id": order_id,
            "order_type": order_type,
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    
    await manager.broadcast_to_drivers(message)
    await manager.broadcast_to_admins(message)
