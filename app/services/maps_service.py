import httpx
from typing import Tuple, Dict, Optional
from .config import settings


class MapsService:
    """Google Maps API integration"""
    
    def __init__(self):
        self.api_key = settings.GOOGLE_MAPS_API_KEY
        self.base_url = "https://maps.googleapis.com/maps/api"
    
    async def calculate_distance(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float
    ) -> Dict:
        """Calculate distance and duration between two points"""
        url = f"{self.base_url}/distancematrix/json"
        params = {
            "origins": f"{origin_lat},{origin_lng}",
            "destinations": f"{dest_lat},{dest_lng}",
            "key": self.api_key
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()
            
            if data["status"] == "OK":
                element = data["rows"][0]["elements"][0]
                if element["status"] == "OK":
                    return {
                        "distance_meters": element["distance"]["value"],
                        "distance_km": element["distance"]["value"] / 1000,
                        "duration_seconds": element["duration"]["value"],
                        "distance_text": element["distance"]["text"],
                        "duration_text": element["duration"]["text"]
                    }
            
            return None
    
    async def geocode_address(self, address: str) -> Optional[Tuple[float, float]]:
        """Convert address to coordinates"""
        url = f"{self.base_url}/geocode/json"
        params = {
            "address": address,
            "key": self.api_key
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()
            
            if data["status"] == "OK" and len(data["results"]) > 0:
                location = data["results"][0]["geometry"]["location"]
                return (location["lat"], location["lng"])
            
            return None
    
    async def reverse_geocode(self, lat: float, lng: float) -> Optional[str]:
        """Convert coordinates to address"""
        url = f"{self.base_url}/geocode/json"
        params = {
            "latlng": f"{lat},{lng}",
            "key": self.api_key
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()
            
            if data["status"] == "OK" and len(data["results"]) > 0:
                return data["results"][0]["formatted_address"]
            
            return None
    
    async def calculate_price(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        base_price: float = 10000,  # Default base price in SYP
        price_per_km: float = 2000   # Default price per km in SYP
    ) -> Optional[float]:
        """Calculate estimated price based on distance"""
        distance_data = await self.calculate_distance(
            origin_lat, origin_lng, dest_lat, dest_lng
        )
        
        if distance_data:
            distance_km = distance_data["distance_km"]
            price = base_price + (distance_km * price_per_km)
            return round(price, 2)
        
        return None


maps_service = MapsService()
