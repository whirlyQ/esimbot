import os
import asyncio
import logging
from solders.keypair import Keypair
import base58

# Generate keypairs for testing
main_wallet_keypair = Keypair()
main_wallet_address = str(main_wallet_keypair.pubkey())
main_wallet_private_key = base58.b58encode(bytes(main_wallet_keypair)).decode('ascii')
dummy_token_account = str(Keypair().pubkey())

# Set environment variables explicitly for testing token amounts
os.environ['TESTING_MODE'] = 'true'
os.environ['TESTING_PAYMENT_MULTIPLIER'] = '1.0'  # 100% of actual amount
os.environ['MOCK_PAYMENT_SUCCESS'] = 'false'  # Don't auto-complete payments
os.environ['SPL_TOKEN_DECIMALS'] = '6'  # 6 decimals (most common for tokens like USDC)
os.environ['SOLANA_MAIN_WALLET'] = main_wallet_address
os.environ['SOLANA_MAIN_WALLET_PRIVATE_KEY'] = main_wallet_private_key
os.environ['SOLANA_MAIN_WALLET_TOKEN_ACCOUNT'] = dummy_token_account
os.environ['SPL_TOKEN_MINT'] = str(Keypair().pubkey())  # Dummy token mint
os.environ['SPL_TOKEN_SYMBOL'] = 'TEST'

# Now import the module after setting environment variables
from solana_payments import get_payment_manager, TESTING_MODE, TESTING_PAYMENT_MULTIPLIER

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_payment_amounts():
    """Test that token amounts are handled correctly."""
    payment_manager = get_payment_manager()
    
    # Show environment settings
    logger.info(f"TESTING_MODE: {TESTING_MODE}")
    logger.info(f"TESTING_PAYMENT_MULTIPLIER: {TESTING_PAYMENT_MULTIPLIER}")
    logger.info(f"SPL_TOKEN_DECIMALS: {os.environ['SPL_TOKEN_DECIMALS']}")
    
    # Test with various amounts
    test_amounts = [1, 10, 100, 1000]
    
    for amount in test_amounts:
        logger.info(f"\nTesting with amount: {amount}")
        
        # Create a payment
        payment = payment_manager.create_payment(amount, user_id="test_user")
        logger.info(f"Created payment with address: {payment.address}")
        logger.info(f"Payment amount: {payment.amount} {os.environ['SPL_TOKEN_SYMBOL']}")
        
        # Force payment to 'completed' state for testing
        payment.status = 'completed'
        payment.token_account = dummy_token_account
        
        # Test creating the token transfer instruction
        token_transfer_ix = payment_manager._create_token_transfer_instruction(
            source=dummy_token_account,
            destination=dummy_token_account,
            owner=payment.address,
            amount=payment.amount
        )
        
        # Extract the amount from the instruction data
        # Token transfer command is 3, followed by the amount as u64 (8 bytes)
        if len(token_transfer_ix.data) >= 9:
            # Extract amount from bytes (little endian)
            amount_bytes = token_transfer_ix.data[1:9]
            actual_amount = int.from_bytes(amount_bytes, byteorder='little')
            expected_amount = payment.amount * (10 ** int(os.environ['SPL_TOKEN_DECIMALS']))
            
            logger.info(f"Amount in instruction: {actual_amount} base units")
            logger.info(f"Expected amount: {expected_amount} base units")
            logger.info(f"Correct amount: {'✓' if actual_amount == expected_amount else '✗'}")
        
        # Try to sweep
        logger.info("Attempting to sweep funds...")
        sweep_result = await payment_manager.sweep_funds(payment.address)
        
        # Check the result
        logger.info(f"Sweep result: {sweep_result}")
        
        if sweep_result['success']:
            # If successful, check if it was mocked
            logger.info(f"Mock transaction: {sweep_result.get('mock', False)}")
            logger.info(f"Missing accounts: {sweep_result.get('missing_accounts', False)}")
        else:
            logger.info(f"Sweep failed: {sweep_result['message']}")

async def main():
    logger.info("Starting token amount test...")
    await test_payment_amounts()
    logger.info("Test completed.")

if __name__ == "__main__":
    asyncio.run(main()) 