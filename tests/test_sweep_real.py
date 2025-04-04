import os
import asyncio
import logging
from solders.keypair import Keypair
import base58

# Generate keypairs for testing
main_wallet_keypair = Keypair()
main_wallet_address = str(main_wallet_keypair.pubkey())
main_wallet_private_key = base58.b58encode(bytes(main_wallet_keypair)).decode('ascii')

# Generate a dummy token account
dummy_token_account = str(Keypair().pubkey())

# Set environment variables explicitly
os.environ['TESTING_MODE'] = 'true'
os.environ['MOCK_PAYMENT_SUCCESS'] = 'false'
os.environ['SOLANA_MAIN_WALLET'] = main_wallet_address
os.environ['SOLANA_MAIN_WALLET_PRIVATE_KEY'] = main_wallet_private_key
os.environ['SOLANA_MAIN_WALLET_TOKEN_ACCOUNT'] = dummy_token_account
os.environ['TEST_TOKEN_ACCOUNT'] = dummy_token_account
os.environ['SPL_TOKEN_MINT'] = str(Keypair().pubkey())  # Dummy token mint

# Now import the module after setting environment variables
from solana_payments import get_payment_manager, TESTING_MODE, MOCK_PAYMENT_SUCCESS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_payment_and_sweep():
    """Test creating a payment, marking it as complete, and sweeping it."""
    payment_manager = get_payment_manager()
    
    # Show mode and environment
    logger.info(f"TESTING_MODE: {TESTING_MODE}")
    logger.info(f"MOCK_PAYMENT_SUCCESS: {MOCK_PAYMENT_SUCCESS}")
    logger.info(f"Main wallet address: {os.environ['SOLANA_MAIN_WALLET']}")
    logger.info(f"Main wallet private key (first 10 chars): {os.environ['SOLANA_MAIN_WALLET_PRIVATE_KEY'][:10]}...")
    logger.info(f"Token account: {os.environ['SOLANA_MAIN_WALLET_TOKEN_ACCOUNT']}")
    logger.info(f"Token mint: {os.environ['SPL_TOKEN_MINT']}")
    
    # Create a payment
    payment_amount = 10  # This will be reduced to 1 if TESTING_MODE is true
    payment = payment_manager.create_payment(payment_amount, user_id="test_user")
    logger.info(f"Created payment with address: {payment.address}")
    logger.info(f"Payment amount: {payment.amount} tokens")
    
    # Mark the payment as complete (simulate receiving the funds)
    payment.status = 'completed'
    payment.token_account = os.getenv('TEST_TOKEN_ACCOUNT')
    logger.info(f"Marked payment as complete with token account: {payment.token_account}")
    
    # Try to sweep the funds
    logger.info("Sweeping funds...")
    sweep_result = await payment_manager.sweep_funds(payment.address)
    
    # Check the result
    logger.info(f"Sweep result: {sweep_result}")
    if sweep_result['success']:
        logger.info(f"Sweep successful: {sweep_result['message']}")
        if 'transaction_signature' in sweep_result:
            logger.info(f"Transaction signature: {sweep_result['transaction_signature']}")
            logger.info(f"Mock transaction: {sweep_result.get('mock', False)}")
    else:
        logger.error(f"Sweep failed: {sweep_result['message']}")
    
    logger.info(f"Final payment status: {payment.status}")
    
    # Now try sweep and confirm
    if sweep_result['success']:
        # Reset the payment status for another test
        payment.status = 'completed'
        logger.info("\nNow testing sweep_and_confirm...")
        confirm_result = await payment_manager.sweep_and_confirm(payment.address)
        logger.info(f"Confirm result: {confirm_result}")
        if confirm_result['success']:
            logger.info(f"Confirm successful: {confirm_result['message']}")
            logger.info(f"Transaction signature: {confirm_result.get('transaction_signature', 'None')}")
            logger.info(f"Mock transaction: {confirm_result.get('mock', False)}")
        else:
            logger.error(f"Confirm failed: {confirm_result['message']}")
        
        logger.info(f"Final payment status after confirm: {payment.status}")

async def main():
    logger.info("Starting payment and sweep test...")
    await test_payment_and_sweep()
    logger.info("Test completed.")

if __name__ == "__main__":
    asyncio.run(main()) 