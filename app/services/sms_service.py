from typing import Optional
from .config import settings


class SMSService:
    """SMS service integration - to be configured later"""
    
    def __init__(self):
        self.provider = settings.SMS_PROVIDER
        self.api_key = settings.SMS_API_KEY
        self.sender_id = settings.SMS_SENDER_ID
    
    async def send_location_link(
        self,
        phone: str,
        token: str,
        order_id: int
    ) -> bool:
        """
        Send SMS with location link to recipient
        
        Args:
            phone: Recipient's phone number
            token: Unique token for location submission
            order_id: Order ID for reference
        
        Returns:
            True if SMS sent successfully, False otherwise
        """
        
        # Generate location link
        # In production, this would be your deployed web app URL
        link = f"https://dot-app.com/set-location/{token}"
        
        message = f"DOT Delivery: Please set your location for order #{order_id}: {link}"
        
        # TODO: Implement actual SMS sending based on provider
        # For now, just log it (will be implemented later)
        print(f"[SMS] To: {phone}, Message: {message}")
        
        # Placeholder return - will be True when SMS provider is configured
        return True
    
    async def send_notification(self, phone: str, message: str) -> bool:
        """Send general notification SMS"""
        # TODO: Implement actual SMS sending
        print(f"[SMS] To: {phone}, Message: {message}")
        return True


sms_service = SMSService()
