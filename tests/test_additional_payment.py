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

async def test_additional_payment():
    """Test adding more funds to an underpaid payment."""
    logger.info("\n=== Testing Additional Payment ===")
    
    # Create a new payment
    expected_amount = 100
    payment = Payment(expected_amount, user_id="test_user")
    logger.info(f"Created payment with address: {payment.address}")
    logger.info(f"Expected payment amount: {payment.amount} {os.environ['SPL_TOKEN_SYMBOL']}")
    
    # Simulate first payment (underpaid)
    initial_amount = 50  # Only 50% of required amount
    payment.token_account = dummy_token_account
    
    # Update with first payment
    logger.info(f"Simulating initial payment of {initial_amount} tokens")
    payment.update_balance(initial_amount)
    
    # Check payment status after first payment
    logger.info(f"Payment status after initial payment: {payment.status}")
    logger.info(f"Amount paid: {payment.actual_balance} tokens")
    logger.info(f"Amount remaining: {payment.amount - payment.actual_balance} tokens")
    
    # Now simulate additional payment
    additional_amount = 30
    total_amount = initial_amount + additional_amount
    
    logger.info(f"Simulating additional payment of {additional_amount} tokens")
    payment_completed = payment.update_balance(total_amount)
    
    # Check payment status after additional payment
    logger.info(f"Payment completed: {payment_completed}")
    logger.info(f"Payment status after additional payment: {payment.status}")
    logger.info(f"Total amount paid: {payment.actual_balance} tokens")
    
    # Check payment history
    logger.info(f"Payment history: {payment.payment_history}")
    
    # Still underpaid, so add more to complete
    final_amount = total_amount + 25  # Add 25 more to reach 105 (overpayment)
    
    logger.info(f"Simulating final payment of {final_amount - total_amount} tokens")
    payment_completed = payment.update_balance(final_amount)
    
    # Check payment status after final payment
    logger.info(f"Payment completed: {payment_completed}")
    logger.info(f"Payment status after final payment: {payment.status}")
    logger.info(f"Final amount paid: {payment.actual_balance} tokens")
    logger.info(f"Overpayment: {payment.actual_balance - payment.amount} tokens")
    
    # Check payment history
    logger.info(f"Final payment history: {payment.payment_history}")
    
    # Verify that the payment is now complete
    assert payment.status == 'completed', "Payment status should be 'completed'"
    assert payment.actual_balance >= payment.amount, "Actual balance should be at least the required amount"
    assert len(payment.payment_history) == 3, "Should have 3 payment entries in history"
    
    return True

async def main():
    logger.info("Starting additional payment test...")
    success = await test_additional_payment()
    logger.info(f"Test {'PASSED' if success else 'FAILED'}")
    logger.info("Test completed.")

if __name__ == "__main__":
    asyncio.run(main()) 