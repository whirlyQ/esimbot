import asyncio
from crypto_payment import CryptoPayment
from service_api import ServiceAPI
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def test_crypto_payment():
    """Test crypto payment functionality"""
    try:
        payment = CryptoPayment()
        # Test payment creation
        result = await payment.create_payment(amount=100.00, currency="USD")
        logger.info(f"Create payment result: {result}")
        
        # If the above succeeds and returns a payment_id, test verification
        if 'payment_id' in result:
            status = await payment.get_payment_status(result['payment_id'])
            logger.info(f"Payment status: {status}")
    except Exception as e:
        logger.error(f"Crypto payment test failed: {str(e)}")

async def test_service_api():
    """Test service API functionality"""
    try:
        service = ServiceAPI()
        # Test order creation
        test_data = {
            "customer_name": "Test User",
            "service_details": "Test Service"
        }
        result = await service.create_order("service1", test_data)
        logger.info(f"Create order result: {result}")
        
        # If the above succeeds and returns an order_id, test status check
        if 'order_id' in result:
            status = await service.get_order_status(result['order_id'])
            logger.info(f"Order status: {status}")
    except Exception as e:
        logger.error(f"Service API test failed: {str(e)}")

async def run_tests():
    """Run all tests"""
    logger.info("Starting bot component tests...")
    
    # Test crypto payment integration
    logger.info("\nTesting Crypto Payment Integration:")
    await test_crypto_payment()
    
    # Test service API integration
    logger.info("\nTesting Service API Integration:")
    await test_service_api()
    
    logger.info("\nTests completed!")

if __name__ == "__main__":
    asyncio.run(run_tests()) 