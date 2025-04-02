import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()

class CryptoPayment:
    def __init__(self):
        self.api_key = os.getenv('CRYPTO_PAYMENT_API_KEY')
        self.base_url = "https://api.cryptopayment-provider.com/v1"  # Replace with actual API URL

    async def create_payment(self, amount: float, currency: str = "USD"):
        """Create a new crypto payment invoice."""
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "amount": amount,
                "currency": currency,
                "supported_cryptocurrencies": ["BTC", "ETH", "USDT"]
            }
            
            async with session.post(
                f"{self.base_url}/create-payment",
                headers=headers,
                json=payload
            ) as response:
                return await response.json()

    async def verify_payment(self, payment_id: str):
        """Verify if a payment has been completed."""
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with session.get(
                f"{self.base_url}/payment/{payment_id}",
                headers=headers
            ) as response:
                return await response.json()

    async def get_payment_status(self, payment_id: str):
        """Get the current status of a payment."""
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with session.get(
                f"{self.base_url}/payment/{payment_id}/status",
                headers=headers
            ) as response:
                return await response.json() 