import os
import asyncio
import logging
import time
from solders.keypair import Keypair
import base58

# Generate keypairs for testing
main_wallet_keypair = Keypair()
main_wallet_address = str(main_wallet_keypair.pubkey())
main_wallet_private_key = base58.b58encode(bytes(main_wallet_keypair)).decode('ascii')
dummy_token_account = str(Keypair().pubkey())

# Set environment variables explicitly for mock testing
os.environ['TESTING_MODE'] = 'true'
os.environ['MOCK_PAYMENT_SUCCESS'] = 'true'
os.environ['MOCK_PAYMENT_SUCCESS_DELAY'] = '2'  # 2 second delay for quicker testing
os.environ['SOLANA_MAIN_WALLET'] = main_wallet_address
os.environ['SOLANA_MAIN_WALLET_PRIVATE_KEY'] = main_wallet_private_key
os.environ['SOLANA_MAIN_WALLET_TOKEN_ACCOUNT'] = dummy_token_account
os.environ['SPL_TOKEN_MINT'] = str(Keypair().pubkey())  # Dummy token mint

# Now import the module after setting environment variables
from solana_payments import get_payment_manager, TESTING_MODE, MOCK_PAYMENT_SUCCESS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_mock_payment():
    """Test the mock payment success feature."""
    payment_manager = get_payment_manager()
    
    # Show environment
    logger.info(f"TESTING_MODE: {TESTING_MODE}")
    logger.info(f"MOCK_PAYMENT_SUCCESS: {MOCK_PAYMENT_SUCCESS}")
    logger.info(f"MOCK_PAYMENT_SUCCESS_DELAY: {os.environ['MOCK_PAYMENT_SUCCESS_DELAY']} seconds")
    
    # Create a payment
    payment_amount = 10  # This will be reduced to 1 in TESTING_MODE
    payment = payment_manager.create_payment(payment_amount, user_id="test_user")
    logger.info(f"Created payment with address: {payment.address}")
    logger.info(f"Payment amount: {payment.amount} tokens")
    
    # Check payment status immediately
    logger.info("Checking payment status immediately...")
    status_result = await payment_manager.check_payment_status(payment.address)
    logger.info(f"Initial status: {status_result['status']}")
    
    # Wait a bit and check again
    wait_time = int(os.environ['MOCK_PAYMENT_SUCCESS_DELAY']) + 1
    logger.info(f"Waiting {wait_time} seconds for mock payment to complete...")
    await asyncio.sleep(wait_time)
    
    # Check payment status again - should be completed now
    status_result = await payment_manager.check_payment_status(payment.address)
    logger.info(f"Status after waiting: {status_result['status']}")
    
    if status_result['status'] == 'completed':
        logger.info("Mock payment completed successfully!")
        
        # Now sweep the funds
        logger.info("Sweeping funds...")
        sweep_result = await payment_manager.sweep_and_confirm(payment.address)
        
        logger.info(f"Sweep result: {sweep_result}")
        logger.info(f"Transaction signature: {sweep_result.get('transaction_signature', 'None')}")
        logger.info(f"Mock transaction: {sweep_result.get('mock', False)}")
        logger.info(f"Final status: {payment.status}")
    else:
        logger.error(f"Mock payment did not complete as expected. Status: {status_result['status']}")

async def main():
    logger.info("Starting mock payment test...")
    await test_mock_payment()
    logger.info("Test completed.")

if __name__ == "__main__":
    asyncio.run(main()) 