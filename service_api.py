import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()

class ServiceAPI:
    def __init__(self):
        self.api_key = os.getenv('SERVICE_API_KEY')
        self.base_url = os.getenv('SERVICE_API_URL')

    async def create_order(self, service_type: str, user_data: dict):
        """Create a new order with the service API."""
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "service_type": service_type,
                "user_data": user_data
            }
            
            async with session.post(
                f"{self.base_url}/orders",
                headers=headers,
                json=payload
            ) as response:
                return await response.json()

    async def get_order_status(self, order_id: str):
        """Get the status of an order."""
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with session.get(
                f"{self.base_url}/orders/{order_id}",
                headers=headers
            ) as response:
                return await response.json()

    async def cancel_order(self, order_id: str):
        """Cancel an existing order."""
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with session.delete(
                f"{self.base_url}/orders/{order_id}",
                headers=headers
            ) as response:
                return await response.json() 