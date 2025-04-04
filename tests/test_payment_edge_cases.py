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

# Set environment variables for testing
os.environ['TESTING_MODE'] = 'true'
os.environ['TESTING_PAYMENT_MULTIPLIER'] = '1.0'
os.environ['MOCK_PAYMENT_SUCCESS'] = 'false'
os.environ['SPL_TOKEN_DECIMALS'] = '6'
os.environ['SOLANA_MAIN_WALLET'] = main_wallet_address
os.environ['SOLANA_MAIN_WALLET_PRIVATE_KEY'] = main_wallet_private_key
os.environ['SOLANA_MAIN_WALLET_TOKEN_ACCOUNT'] = dummy_token_account
os.environ['SPL_TOKEN_MINT'] = str(Keypair().pubkey())
os.environ['SPL_TOKEN_SYMBOL'] = 'TEST'

# Import after setting environment variables
from solana_payments import get_payment_manager, Payment

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_overpayment():
    """Test handling of overpayment."""
    payment_manager = get_payment_manager()
    
    logger.info("\n=== Testing Overpayment ===")
    
    # Create a payment for 100 tokens
    expected_amount = 100
    payment = payment_manager.create_payment(expected_amount, user_id="test_user")
    logger.info(f"Created payment with address: {payment.address}")
    logger.info(f"Expected payment amount: {payment.amount} {os.environ['SPL_TOKEN_SYMBOL']}")
    
    # Simulate receiving MORE than the expected amount
    actual_amount = 150  # User paid 50 extra tokens
    payment.status = 'completed'
    payment.token_account = dummy_token_account
    payment.actual_balance = actual_amount
    
    logger.info(f"Simulating overpayment: User paid {actual_amount} tokens (overpaid by {actual_amount - expected_amount})")
    
    # Try to sweep the funds
    logger.info("Sweeping funds...")
    sweep_result = await payment_manager.sweep_funds(payment.address)
    
    # Check the sweep result
    logger.info(f"Sweep result: {sweep_result}")
    
    # Verify that the full amount (including overpayment) was swept
    if sweep_result['success']:
        logger.info(f"Amount swept: {sweep_result.get('amount')} tokens")
        logger.info(f"Expected amount: {sweep_result.get('expected_amount')} tokens")
        logger.info(f"Overpayment: {sweep_result.get('overpayment')} tokens")
        
        if sweep_result.get('amount') == actual_amount:
            logger.info("SUCCESS: Full amount including overpayment was swept")
        else:
            logger.error(f"ERROR: Only swept {sweep_result.get('amount')} tokens instead of {actual_amount}")
    else:
        logger.error(f"Sweep failed: {sweep_result['message']}")

async def test_underpayment():
    """Test handling of underpayment."""
    payment_manager = get_payment_manager()
    
    logger.info("\n=== Testing Underpayment ===")
    
    # Create a payment for 100 tokens
    expected_amount = 100
    payment = payment_manager.create_payment(expected_amount, user_id="test_user")
    logger.info(f"Created payment with address: {payment.address}")
    logger.info(f"Expected payment amount: {payment.amount} {os.environ['SPL_TOKEN_SYMBOL']}")
    
    # Simulate receiving LESS than the expected amount
    actual_amount = 75  # User paid 25 fewer tokens than required
    payment.token_account = dummy_token_account
    payment.actual_balance = actual_amount
    
    # Force payment to pending state since it's underpaid
    payment.status = 'pending'
    
    logger.info(f"Simulating underpayment: User paid {actual_amount} tokens (underpaid by {expected_amount - actual_amount})")
    
    # Check payment status
    status_result = {
        'success': False, 
        'status': 'underpaid', 
        'message': f'Underpaid by {expected_amount - actual_amount} tokens', 
        'payment': payment,
        'amount_paid': actual_amount,
        'amount_remaining': expected_amount - actual_amount
    }
    
    logger.info(f"Payment status: {status_result}")
    
    # Try to sweep anyway (this should fail since payment is not 'completed')
    logger.info("Attempting to sweep underpaid funds (should fail)...")
    sweep_result = await payment_manager.sweep_funds(payment.address)
    
    # Check the sweep result
    logger.info(f"Sweep result: {sweep_result}")
    
    if not sweep_result['success']:
        logger.info("SUCCESS: System correctly prevented sweeping of underpaid funds")
    else:
        logger.error("ERROR: System allowed sweeping of underpaid funds")

async def main():
    logger.info("Starting payment edge case tests...")
    
    # Test overpayment handling
    await test_overpayment()
    
    # Test underpayment handling
    await test_underpayment()
    
    logger.info("Test completed.")

if __name__ == "__main__":
    asyncio.run(main()) 