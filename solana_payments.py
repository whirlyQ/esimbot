import os
import time
import logging
import asyncio
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import base64

# Setup logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import Solana modules
from solana.rpc.api import Client
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solana.transaction import Transaction
from solders.system_program import TransferParams, transfer
from solana.rpc.types import TxOpts
from solana.rpc.commitment import Commitment
from solders.instruction import Instruction, AccountMeta
from solders.hash import Hash
from base58 import b58decode, b58encode

# Constants
PAYMENT_TIMEOUT_MINUTES = 10
SPL_TOKEN_MINT = os.getenv('SPL_TOKEN_MINT')  # The mint address of the SPL token
SPL_TOKEN_SYMBOL = os.getenv('SPL_TOKEN_SYMBOL', 'SPL')  # Token symbol for display
MAIN_WALLET_ADDRESS = os.getenv('SOLANA_MAIN_WALLET')  # Main wallet to sweep funds to
MAIN_WALLET_PRIVATE_KEY = os.getenv('SOLANA_MAIN_WALLET_PRIVATE_KEY')  # Private key for signing
MAIN_WALLET_TOKEN_ACCOUNT = os.getenv('SOLANA_MAIN_WALLET_TOKEN_ACCOUNT')  # Token account for the SPL token
SOLANA_NETWORK = os.getenv('SOLANA_NETWORK', 'devnet')  # 'devnet', 'testnet', or 'mainnet-beta'

# Testing parameters
TESTING_MODE = os.getenv('TESTING_MODE', 'false').lower() == 'true'  # Reduced token amounts but real tx
TESTING_PAYMENT_MULTIPLIER = float(os.getenv('TESTING_PAYMENT_MULTIPLIER', '0.01'))  # Default to 1% of actual cost
MOCK_PAYMENT_SUCCESS = os.getenv('MOCK_PAYMENT_SUCCESS', 'false').lower() == 'true'  # Fully simulated tx
try:
    MOCK_PAYMENT_SUCCESS_DELAY = int(os.getenv('MOCK_PAYMENT_SUCCESS_DELAY', '10'))  # Seconds
except ValueError:
    # In case there's an issue with the environment variable format
    logger.warning("Invalid MOCK_PAYMENT_SUCCESS_DELAY format, using default value of 10 seconds")
    MOCK_PAYMENT_SUCCESS_DELAY = 10

if TESTING_MODE:
    logger.info(f"TESTING_MODE is enabled - token amounts will be multiplied by {TESTING_PAYMENT_MULTIPLIER}")
if MOCK_PAYMENT_SUCCESS:
    logger.info("MOCK_PAYMENT_SUCCESS is enabled - transactions will be simulated")

# SPL Token program ID - this is a fixed value across all Solana networks
# It's the program that handles all SPL token operations (creation, transfer, etc.)
TOKEN_PROGRAM_ID = os.getenv('SPL_TOKEN_PROGRAM_ID', 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA')

# Configure Solana client
if SOLANA_NETWORK == 'mainnet-beta':
    SOLANA_URL = 'https://api.mainnet-beta.solana.com'
elif SOLANA_NETWORK == 'testnet':
    SOLANA_URL = 'https://api.testnet.solana.com'
else:
    SOLANA_URL = 'https://api.devnet.solana.com'

solana_client = Client(SOLANA_URL)

# Create a direct HTTP client for RPC calls
def make_rpc_request(method, params=None, retries=3, retry_delay=1):
    """Make a direct JSON-RPC request to the Solana node with retries."""
    if params is None:
        params = []
    
    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }
    
    logger.debug(f"Making RPC request: {method} with params: {params}")
    
    for attempt in range(retries):
        try:
            response = requests.post(SOLANA_URL, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    logger.error(f"RPC error: {result['error']}")
                    # Check if this is a blockhash error - we need special handling
                    if 'BlockhashNotFound' in str(result) or 'Blockhash not found' in str(result):
                        logger.warning(f"Blockhash not found error, retrying with new blockhash")
                        if method == "sendTransaction" and attempt < retries - 1:
                            # Sleep a bit longer for blockhash errors
                            time.sleep(retry_delay * 2)
                            continue
                    return result  # Return the error result so caller can handle it
                logger.debug(f"RPC response received for {method}")
                return result
            else:
                logger.error(f"RPC request failed with status {response.status_code}: {response.text}")
                if attempt < retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds... (attempt {attempt+1}/{retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                continue
        except Exception as e:
            logger.error(f"Error making RPC request: {str(e)}")
            if attempt < retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds... (attempt {attempt+1}/{retries})")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                return None
    
    return None

class Payment:
    def __init__(self, amount, user_id=None, package_id=None):
        self.amount = amount
        self.user_id = user_id
        self.package_id = package_id
        self.keypair = Keypair()
        self.address = str(self.keypair.pubkey())
        self.created_at = datetime.now()
        self.expires_at = self.created_at + timedelta(minutes=PAYMENT_TIMEOUT_MINUTES)
        self.status = 'pending'  # pending, completed, expired, failed, swept
        self.transaction_signature = None
        self.token_account = None  # Store the token account address once found
        self.actual_balance = None  # Store the actual token balance for overpayment checking
        self.previous_balance = 0  # Track previous balance for detecting additional payments
        self.payment_history = []  # Track payment history
        self.topup_ordered = False  # Flag to track if topup has been ordered
        self.topup_order_id = None  # Track the Airalo order ID
        self.iccid = None  # Store the ICCID for this payment
        logger.info(f"Created payment address {self.address} for amount {amount} {SPL_TOKEN_SYMBOL}")

    def is_expired(self):
        """Check if the payment has expired."""
        return datetime.now() > self.expires_at

    def time_remaining(self):
        """Get the remaining time for payment in seconds."""
        if self.is_expired():
            return 0
        return (self.expires_at - datetime.now()).total_seconds()

    def update_balance(self, new_balance):
        """Update the payment balance and track payment history."""
        previous = self.actual_balance or 0
        
        # Only record if balance increases
        if new_balance > previous:
            added_amount = new_balance - previous
            
            # Convert to token units for logging if needed
            token_decimals = int(os.getenv('SPL_TOKEN_DECIMALS', '9'))
            new_balance_tokens = new_balance / (10 ** token_decimals)
            previous_tokens = previous / (10 ** token_decimals)
            added_tokens = added_amount / (10 ** token_decimals)
            
            # Record the payment in history
            self.payment_history.append({
                'timestamp': datetime.now().isoformat(),
                'previous_balance': previous,
                'new_balance': new_balance,
                'added_amount': added_amount
            })
            
            logger.info(f"Payment {self.address} received {added_amount} tokens (total now: {new_balance})")
            
            # Update actual balance
            self.previous_balance = previous
            self.actual_balance = new_balance
            
            # Check if payment is now complete
            if new_balance >= self.amount and self.status == 'pending':
                self.status = 'completed'
                
                # For raw token amounts, only show overpayment if significant
                # Check if the amounts are in raw token units
                is_raw = self.amount < 1000 and new_balance > 1000
                
                if is_raw:
                    # Only log overpayment if it's more than 1% over required amount
                    overpayment = new_balance - self.amount
                    if overpayment > (self.amount * 0.01):
                        logger.info(f"Overpayment detected: {overpayment} extra tokens (raw units)")
                else:
                    # For standard token amounts, calculate normally
                    if new_balance > self.amount:
                        overpayment = new_balance - self.amount
                        logger.info(f"Overpayment detected: {overpayment} extra tokens")
                
                logger.info(f"Payment {self.address} now complete with balance {new_balance}")
                return True
                
        return False

    def to_dict(self):
        """Convert payment to dictionary for storage."""
        return {
            'amount': self.amount,
            'user_id': self.user_id,
            'package_id': self.package_id,
            'address': self.address,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'status': self.status,
            'transaction_signature': self.transaction_signature,
            'token_account': self.token_account,
            'actual_balance': self.actual_balance,
            'previous_balance': self.previous_balance,
            'payment_history': self.payment_history,
            'topup_ordered': self.topup_ordered,
            'topup_order_id': self.topup_order_id,
            'iccid': self.iccid,
            # Store private key securely (should be encrypted in production)
            'private_key': bytes(self.keypair.secret_key).hex()
        }

    @classmethod
    def from_dict(cls, data):
        """Create a Payment instance from dictionary data."""
        payment = cls(
            amount=data['amount'],
            user_id=data['user_id'],
            package_id=data['package_id']
        )
        payment.address = data['address']
        payment.created_at = datetime.fromisoformat(data['created_at'])
        payment.expires_at = datetime.fromisoformat(data['expires_at'])
        payment.status = data['status']
        payment.transaction_signature = data['transaction_signature']
        payment.token_account = data.get('token_account')
        payment.actual_balance = data.get('actual_balance')
        payment.previous_balance = data.get('previous_balance')
        payment.payment_history = data.get('payment_history', [])
        payment.topup_ordered = data.get('topup_ordered', False)
        payment.topup_order_id = data.get('topup_order_id')
        payment.iccid = data.get('iccid')
        
        # Reconstruct the keypair from private key
        if 'private_key' in data:
            from solders.keypair import Keypair
            private_key_bytes = bytes.fromhex(data['private_key'])
            payment.keypair = Keypair.from_bytes(private_key_bytes)
        
        return payment

class PaymentManager:
    def __init__(self):
        self.payments = {}  # Dictionary to store payments by address
        
        if not SPL_TOKEN_MINT:
            logger.warning("SPL_TOKEN_MINT not set in environment variables")
        if not MAIN_WALLET_ADDRESS:
            logger.warning("SOLANA_MAIN_WALLET not set in environment variables")
        if not MAIN_WALLET_PRIVATE_KEY:
            logger.warning("SOLANA_MAIN_WALLET_PRIVATE_KEY not set in environment variables")
        if not MAIN_WALLET_TOKEN_ACCOUNT:
            logger.warning("SOLANA_MAIN_WALLET_TOKEN_ACCOUNT not set in environment variables")
        
        logger.info(f"Payment manager initialized for {SOLANA_NETWORK}")
        logger.info(f"Using token: {SPL_TOKEN_SYMBOL} ({SPL_TOKEN_MINT or 'Not Set'})")

    def create_payment(self, amount, user_id=None, package_id=None):
        """Create a new payment and return the address to pay to."""
        # In testing mode, multiply token amount by TESTING_PAYMENT_MULTIPLIER
        if TESTING_MODE and amount > 0:
            original_amount = amount
            amount = max(1, int(amount * TESTING_PAYMENT_MULTIPLIER))  # Ensure at least 1 token
            logger.info(f"TESTING_MODE: Reduced payment amount from {original_amount} to {amount} {SPL_TOKEN_SYMBOL}")
        
        payment = Payment(amount, user_id, package_id)
        self.payments[payment.address] = payment
        return payment

    async def check_payment_status(self, payment_address):
        """Check if a payment has been received at the given address."""
        try:
            if payment_address not in self.payments:
                return {'success': False, 'message': 'Payment not found'}
            
            payment = self.payments[payment_address]
            
            if payment.status in ['completed', 'swept']:
                return {'success': True, 'status': payment.status, 'payment': payment}
            
            if payment.is_expired():
                payment.status = 'expired'
                return {'success': False, 'status': 'expired', 'message': 'Payment expired', 'payment': payment}
            
            # For testing: mock successful payment after a delay 
            # Note that this is different from TESTING_MODE which only reduces token amounts
            if MOCK_PAYMENT_SUCCESS:
                # Calculate time since payment creation
                time_since_creation = (datetime.now() - payment.created_at).total_seconds()
                
                # If enough time has passed, mark payment as completed
                if time_since_creation >= MOCK_PAYMENT_SUCCESS_DELAY:
                    payment.status = 'completed'
                    payment.transaction_signature = f"mocked_payment_{int(time.time())}"
                    
                    # Create a fake token account - use a prefix that we can detect later
                    payment.token_account = f"mocked_token_account_{int(time.time())}"
                    
                    logger.info(f"MOCK: Payment completed for {payment_address}")
                    return {'success': True, 'status': 'completed', 'payment': payment}
                else:
                    logger.info(f"MOCK: Payment pending, will complete in {MOCK_PAYMENT_SUCCESS_DELAY - time_since_creation:.1f} seconds")
            
            # Real payment checking with SPL token
            if SPL_TOKEN_MINT and not MOCK_PAYMENT_SUCCESS:
                try:
                    # Get token accounts for this address with the specified mint
                    # Convert string address to Pubkey object
                    payment_pubkey = Pubkey.from_string(payment_address)
                    mint_pubkey = Pubkey.from_string(SPL_TOKEN_MINT)
                    
                    logger.info(f"Checking token accounts for address {payment_address} with mint {SPL_TOKEN_MINT}")
                    
                    # Make a direct RPC call to get token accounts
                    params = [
                        str(payment_pubkey),
                        {"mint": str(mint_pubkey)},
                        {"encoding": "jsonParsed", "commitment": "confirmed"}
                    ]
                    
                    response_data = make_rpc_request("getTokenAccountsByOwner", params)
                    
                    if response_data and 'result' in response_data and 'value' in response_data['result']:
                        token_accounts = response_data['result']['value']
                        logger.info(f"Found {len(token_accounts)} token accounts via direct RPC")
                        
                        for account in token_accounts:
                            token_account_address = account['pubkey']
                            account_data = account['account']['data']
                            
                            # For jsonParsed encoding, the parsed data is in the parsed field
                            if 'parsed' in account_data:
                                parsed_data = account_data['parsed']
                                if 'info' in parsed_data and 'tokenAmount' in parsed_data['info']:
                                    token_amount = parsed_data['info']['tokenAmount']
                                    token_balance = int(token_amount['amount'])
                                    
                                    # Get token decimals from response or environment
                                    token_decimals = int(token_amount.get('decimals', os.getenv('SPL_TOKEN_DECIMALS', '9')))
                                    
                                    # Convert to human-readable amount for logging
                                    display_balance = token_balance / (10 ** token_decimals)
                                    logger.info(f"Found token account {token_account_address} with balance {token_balance} raw units ({display_balance} tokens)")
                                    
                                    # Store the account address for later use in sweeping
                                    payment.token_account = token_account_address
                                    
                                    # Check what unit the payment amount is in
                                    # If payment.amount is small (like 1) but token_balance is large (like 1000000),
                                    # then payment.amount is likely in tokens, not raw units
                                    if payment.amount < 1000 and token_balance > 1000:
                                        # Convert payment amount to raw units for comparison
                                        payment_amount_raw = payment.amount * (10 ** token_decimals)
                                        logger.info(f"Converting payment amount {payment.amount} to raw units: {payment_amount_raw}")
                                        
                                        # Check if payment is complete based on raw units
                                        if token_balance >= payment_amount_raw:
                                            payment.status = 'completed'
                                            if not payment.transaction_signature:
                                                payment.transaction_signature = f"token_transfer_{int(time.time())}"
                                            
                                            # Store the actual balance
                                            payment.actual_balance = token_balance
                                            
                                            # Check for overpayment
                                            if token_balance > payment_amount_raw:
                                                overpayment = token_balance - payment_amount_raw
                                                overpayment_display = overpayment / (10 ** token_decimals)
                                                logger.info(f"Overpayment detected: {overpayment} raw units ({overpayment_display} tokens)")
                                            
                                            logger.info(f"Payment completed: {payment_address} with balance {token_balance} raw units ({display_balance} tokens)")
                                            return {'success': True, 'status': 'completed', 'payment': payment}
                                        else:
                                            # Underpayment in raw units
                                            underpayment = payment_amount_raw - token_balance
                                            underpayment_display = underpayment / (10 ** token_decimals)
                                            
                                            logger.info(f"Underpayment detected: {payment_address} has {token_balance} raw units, needs {underpayment} more")
                                            
                                            # Update payment record with current balance
                                            payment.update_balance(token_balance)
                                            
                                            return {
                                                'success': False, 
                                                'status': 'underpaid', 
                                                'message': f'Underpaid by {underpayment_display} tokens', 
                                                'payment': payment,
                                                'amount_paid': display_balance,
                                                'amount_remaining': underpayment_display,
                                                'payment_history': payment.payment_history
                                            }
                                    else:
                                        # Normal case - direct comparison
                                        # Update balance and track payment history
                                        payment_completed = payment.update_balance(token_balance)
                                        
                                        # If payment is now complete
                                        if payment_completed or payment.status == 'completed':
                                            # Create a transaction signature if one doesn't exist
                                            if not payment.transaction_signature:
                                                payment.transaction_signature = f"token_transfer_{int(time.time())}"
                                                
                                            logger.info(f"Payment completed: {payment_address} with balance {token_balance}")
                                            return {'success': True, 'status': 'completed', 'payment': payment}
                                        else:
                                            # Handle underpayment - we found a balance but it's not enough
                                            underpayment = payment.amount - token_balance
                                            logger.info(f"Underpayment detected: {payment_address} has {token_balance} tokens, needs {underpayment} more")
                                            
                                            return {
                                                'success': False, 
                                                'status': 'underpaid', 
                                                'message': f'Underpaid by {underpayment} tokens', 
                                                'payment': payment,
                                                'amount_paid': token_balance,
                                                'amount_remaining': underpayment,
                                                'payment_history': payment.payment_history
                                            }
                except Exception as e:
                    logger.error(f"Error checking token balance: {str(e)}")
                    import traceback
                    logger.error(f"Token check error traceback: {traceback.format_exc()}")
            
            # Fallback to checking regular SOL balance for testing
            try:
                # Convert string address to Pubkey object
                payment_pubkey = Pubkey.from_string(payment_address)
                
                # Use direct RPC call for consistency
                params = [str(payment_pubkey), {"commitment": "confirmed"}]
                
                response_data = make_rpc_request("getBalance", params)
                
                if response_data and 'result' in response_data and 'value' in response_data['result']:
                    balance = response_data['result']['value']
                    logger.info(f"Found SOL balance: {balance} for address {payment_address}")
                    
                    if balance > 0:
                        # For testing/demo purposes - in production you'd want to verify the actual token
                        payment.status = 'completed'
                        payment.transaction_signature = f"sol_balance_{int(time.time())}"
                        logger.info(f"Payment completed via SOL balance: {payment_address}")
                        return {'success': True, 'status': 'completed', 'payment': payment}
            except Exception as e:
                logger.error(f"Error checking SOL balance: {str(e)}")
                import traceback
                logger.error(f"SOL check error traceback: {traceback.format_exc()}")
            
            # If we get here, payment is still pending
            return {
                'success': False, 
                'status': 'pending', 
                'message': 'Payment pending', 
                'expires_in': payment.time_remaining(),
                'payment': payment
            }
        
        except Exception as e:
            logger.error(f"Error checking payment status: {str(e)}")
            return {'success': False, 'message': f"Error checking payment: {str(e)}"}

    # Helper function to create SPL token transfer instruction
    def _create_token_transfer_instruction(self, source, destination, owner, amount):
        """Create a token transfer instruction for SPL tokens."""
        token_program_id = Pubkey.from_string(TOKEN_PROGRAM_ID)
        source_pubkey = Pubkey.from_string(source)
        destination_pubkey = Pubkey.from_string(destination)
        owner_pubkey = Pubkey.from_string(owner)
        
        # Get the token decimals from env
        token_decimals = int(os.getenv('SPL_TOKEN_DECIMALS', '9'))
        
        # Check if amount is already in raw units (when it's over 10^(decimals-1) for a token)
        is_raw_units = amount >= (10 ** (token_decimals - 1))
        
        # Calculate display amount and raw amount
        if is_raw_units:
            display_amount = amount / (10 ** token_decimals)
            actual_amount = amount  # Already in raw units
            logger.info(f"Amount {amount} is in raw units (equals {display_amount} tokens)")
        else:
            display_amount = amount
            actual_amount = amount * (10 ** token_decimals)
            logger.info(f"Converting {display_amount} tokens to {actual_amount} raw units")
        
        logger.info(f"Creating token transfer instruction for {display_amount} tokens ({actual_amount} raw units)")
        
        # Create proper AccountMeta objects
        keys = [
            AccountMeta(pubkey=source_pubkey, is_signer=False, is_writable=True),
            AccountMeta(pubkey=destination_pubkey, is_signer=False, is_writable=True),
            AccountMeta(pubkey=owner_pubkey, is_signer=True, is_writable=False)
        ]
        
        # Token transfer command is 3, followed by the amount as a u64
        data = bytes([3]) + actual_amount.to_bytes(8, 'little')
        
        return Instruction(
            program_id=token_program_id,
            accounts=keys,
            data=data
        )

    async def sweep_funds(self, payment_address):
        """Sweep funds from a payment address to the main wallet."""
        try:
            from solana.transaction import Transaction
            from solders.hash import Hash
            from solders.pubkey import Pubkey
            from solders.signature import Signature
            
            if payment_address not in self.payments:
                return {'success': False, 'message': 'Payment not found'}
            
            payment = self.payments[payment_address]
            
            if payment.status != 'completed':
                return {'success': False, 'message': f'Payment not completed: {payment.status}'}
            
            if not MAIN_WALLET_ADDRESS:
                return {'success': False, 'message': 'Main wallet not configured'}
            
            if not MAIN_WALLET_PRIVATE_KEY:
                return {'success': False, 'message': 'Main wallet private key not configured'}
            
            if not MAIN_WALLET_TOKEN_ACCOUNT:
                return {'success': False, 'message': 'Main wallet token account not configured'}
            
            if not payment.token_account:
                return {'success': False, 'message': 'No token account found for payment address'}
                
            # Special handling for mocked token accounts
            if payment.token_account.startswith('mocked_'):
                logger.info(f"Mocked token account detected: {payment.token_account}")
                logger.info("Simulating sweep without sending transaction")
                txn_signature = f"mock_sweep_{int(time.time())}"
                payment.status = 'swept'
                payment.transaction_signature = txn_signature
                
                return {
                    'success': True, 
                    'message': 'Simulated sweep from mocked token account', 
                    'transaction_signature': txn_signature, 
                    'mock': True
                }
            
            # If MOCK_PAYMENT_SUCCESS is enabled, simulate the sweep without real transactions
            if MOCK_PAYMENT_SUCCESS:
                logger.info(f"MOCK_PAYMENT_SUCCESS: Simulating sweep without sending transaction")
                txn_signature = f"mock_sweep_{int(time.time())}"
                payment.status = 'swept'
                payment.transaction_signature = txn_signature
                
                return {
                    'success': True, 
                    'message': 'Simulated sweep (MOCK_PAYMENT_SUCCESS enabled)', 
                    'transaction_signature': txn_signature, 
                    'mock': True
                }
                
            # For real transactions (regardless of TESTING_MODE)
            try:
                # Create main wallet keypair from private key
                try:
                    logger.info("Attempting to parse main wallet private key")
                    
                    # Try different formats for wallet private keys
                    keypair = None
                    error_messages = []
                    
                    # 1. Try as hex string
                    try:
                        private_key_bytes = bytes.fromhex(MAIN_WALLET_PRIVATE_KEY)
                        keypair = Keypair.from_bytes(private_key_bytes)
                        logger.info("Successfully parsed private key as hex string")
                    except Exception as e:
                        error_messages.append(f"Hex decode failed: {str(e)}")
                    
                    # 2. Try as base58 string (common export format)
                    if not keypair:
                        try:
                            private_key_bytes = b58decode(MAIN_WALLET_PRIVATE_KEY)
                            keypair = Keypair.from_bytes(private_key_bytes)
                            logger.info("Successfully parsed private key as base58 string")
                        except Exception as e:
                            error_messages.append(f"Base58 decode failed: {str(e)}")
                    
                    # 3. Try as array of bytes (Uint8Array)
                    if not keypair and MAIN_WALLET_PRIVATE_KEY.startswith('[') and MAIN_WALLET_PRIVATE_KEY.endswith(']'):
                        try:
                            import json
                            private_key_array = json.loads(MAIN_WALLET_PRIVATE_KEY)
                            private_key_bytes = bytes(private_key_array)
                            keypair = Keypair.from_bytes(private_key_bytes)
                            logger.info("Successfully parsed private key as byte array")
                        except Exception as e:
                            error_messages.append(f"Array format failed: {str(e)}")
                    
                    # If we have a keypair, use it
                    if keypair:
                        main_wallet_keypair = keypair
                    else:
                        # Log all errors and raise exception
                        logger.error(f"Failed to parse private key: {'; '.join(error_messages)}")
                        raise ValueError(f"Could not parse private key in any format: {'; '.join(error_messages)}")
                    
                    # Verify the public key matches what we expect
                    derived_pubkey = str(main_wallet_keypair.pubkey())
                    logger.info(f"Derived public key: {derived_pubkey}")
                    if derived_pubkey != MAIN_WALLET_ADDRESS:
                        logger.warning(f"Warning: Derived public key {derived_pubkey} doesn't match expected wallet address {MAIN_WALLET_ADDRESS}")
                        return {'success': False, 'message': f'Private key does not match wallet address {MAIN_WALLET_ADDRESS}'}
                
                except Exception as e:
                    logger.error(f"Error parsing private key: {str(e)}")
                    return {'success': False, 'message': f'Error parsing private key: {str(e)}'}
                
                # Get a blockhash for the transaction
                blockhash_str = await self.get_blockhash_simple(commitment="confirmed")
                if not blockhash_str:
                    return {'success': False, 'message': 'Failed to get blockhash for transaction'}
                
                blockhash_bytes = b58decode(blockhash_str)
                blockhash = Hash(blockhash_bytes)
                
                # Check the token account balance 
                actual_token_balance = await self.verify_token_balance(payment.token_account)
                if actual_token_balance <= 0:
                    return {'success': False, 'message': 'No tokens found in account to sweep'}
                
                # Get token decimals from environment
                token_decimals = int(os.getenv('SPL_TOKEN_DECIMALS', '6'))
                
                # Create the transaction
                tx = Transaction(
                    fee_payer=main_wallet_keypair.pubkey(),
                    recent_blockhash=blockhash
                )
                
                # Create and add the token transfer instruction
                token_program_id = Pubkey.from_string(TOKEN_PROGRAM_ID)
                source_pubkey = Pubkey.from_string(payment.token_account)
                destination_pubkey = Pubkey.from_string(MAIN_WALLET_TOKEN_ACCOUNT)
                owner_pubkey = Pubkey.from_string(payment_address)
                
                # Token transfer command is 3 (transfer), followed by the amount as a u64
                data = bytes([3]) + actual_token_balance.to_bytes(8, 'little')
                
                # Create proper account metas
                keys = [
                    AccountMeta(pubkey=source_pubkey, is_signer=False, is_writable=True),
                    AccountMeta(pubkey=destination_pubkey, is_signer=False, is_writable=True),
                    AccountMeta(pubkey=owner_pubkey, is_signer=True, is_writable=False)
                ]
                
                # Create and add the instruction
                transfer_ix = Instruction(
                    program_id=token_program_id,
                    accounts=keys,
                    data=data
                )
                
                tx.add(transfer_ix)
                
                # Sign the transaction
                signers = [main_wallet_keypair, payment.keypair]
                tx.sign(*signers)
                
                # Serialize the transaction
                serialized_tx = tx.serialize()
                serialized_tx_base64 = base64.b64encode(serialized_tx).decode('ascii')
                
                # Send the transaction
                logger.info(f"Sending transaction to sweep {actual_token_balance} tokens from {payment.token_account} to {MAIN_WALLET_TOKEN_ACCOUNT}")
                
                # On mainnet-beta, use more aggressive transaction options
                tx_options = {
                    "encoding": "base64",
                    "skipPreflight": True,  # Skip client-side simulation to prevent blockhash errors
                    "maxRetries": 5,        # Allow RPC node to retry transaction
                }
                
                # Add additional options for mainnet
                if SOLANA_NETWORK == 'mainnet-beta':
                    tx_options["preflightCommitment"] = "processed"  # Use faster commitment level for preflight
                
                send_params = [serialized_tx_base64, tx_options]
                
                signature_response = make_rpc_request("sendTransaction", send_params)
                
                if signature_response and 'result' in signature_response:
                    txn_signature = signature_response['result']
                    logger.info(f"Transaction sent: {txn_signature}")
                    
                    # Mark as swept
                    payment.status = 'swept'
                    payment.transaction_signature = txn_signature
                    
                    # Calculate display amount
                    display_amount = actual_token_balance / (10 ** token_decimals)
                    
                    return {
                        'success': True,
                        'message': f'Tokens swept to main wallet: {display_amount} {SPL_TOKEN_SYMBOL}',
                        'transaction_signature': txn_signature,
                        'amount_raw': actual_token_balance,
                        'amount_display': display_amount
                    }
                else:
                    # Get specific error details for better debugging
                    error_msg = "Unknown error"
                    error_code = None
                    error_data = None
                    
                    if signature_response and 'error' in signature_response:
                        error = signature_response['error']
                        error_msg = error.get('message', 'Unknown error')
                        error_code = error.get('code')
                        error_data = error.get('data', {})
                        
                        # Check if this is a blockhash error
                        if 'BlockhashNotFound' in str(error) or 'Blockhash not found' in str(error):
                            logger.error(f"Blockhash error detected: {error_msg}")
                            
                            # Try an alternative approach for blockhash errors on mainnet
                            if SOLANA_NETWORK == 'mainnet-beta':
                                # Mark as swept with special status to indicate it needs manual handling
                                payment.status = 'sweep_pending'
                                logger.warning(f"Setting payment to sweep_pending status due to blockhash errors")
                                return {
                                    'success': True,
                                    'message': 'Payment marked for sweeping (blockhash error)',
                                    'error': error_msg,
                                    'needs_manual_handling': True
                                }
                    
                    logger.error(f"Failed to send sweep transaction: {error_msg}")
                    
                    if error_code:
                        logger.error(f"Error code: {error_code}")
                    
                    if error_data:
                        logger.error(f"Error data: {error_data}")
                        
                        # Log transaction simulation errors if available
                        if 'logs' in error_data and error_data['logs']:
                            for log in error_data['logs']:
                                logger.error(f"Transaction log: {log}")
                    
                    return {
                        'success': False, 
                        'message': f'Failed to send sweep transaction: {error_msg}',
                        'error_code': error_code,
                        'error_data': error_data
                    }
                
            except Exception as e:
                logger.error(f"Error creating sweep transaction: {str(e)}")
                import traceback
                logger.error(f"Sweep error traceback: {traceback.format_exc()}")
                return {'success': False, 'message': f'Error creating sweep transaction: {str(e)}'}
                
        except Exception as e:
            logger.error(f"Error sweeping funds: {str(e)}")
            import traceback
            logger.error(f"Sweep error traceback: {traceback.format_exc()}")
            return {'success': False, 'message': f"Error sweeping funds: {str(e)}"}

    async def sweep_and_confirm(self, payment_address, max_confirmations=10, confirmation_interval=2):
        """Sweep funds and wait for confirmation of the transaction."""
        try:
            # First attempt to sweep the funds
            sweep_result = await self.sweep_funds(payment_address)
            if not sweep_result['success']:
                return sweep_result
            
            # Get the transaction signature from the result
            txn_signature = sweep_result.get('transaction_signature')
            if not txn_signature:
                txn_signature = self.payments[payment_address].transaction_signature
            
            # For mock transactions, just return success
            if sweep_result.get('mock', False):
                # Mark as confirmed
                self.payments[payment_address].status = 'swept_confirmed'
                return {
                    'success': True, 
                    'status': 'confirmed', 
                    'message': sweep_result.get('message', 'Transaction processed'),
                    'transaction_signature': txn_signature,
                    'mock': True
                }
            
            # For real transactions, check confirmation status
            logger.info(f"Waiting for confirmation of transaction {txn_signature}...")
            
            # Wait for confirmations
            for attempt in range(max_confirmations):
                logger.info(f"Checking transaction status (attempt {attempt+1}/{max_confirmations})...")
                
                # Check transaction status
                status_response = make_rpc_request("getSignatureStatuses", [[txn_signature]])
                
                if status_response and 'result' in status_response and 'value' in status_response['result']:
                    statuses = status_response['result']['value']
                    
                    if statuses and statuses[0] != None:
                        status_obj = statuses[0]
                        
                        # Check for errors
                        if status_obj.get('err'):
                            logger.error(f"Transaction failed: {status_obj['err']}")
                            self.payments[payment_address].status = 'sweep_failed'
                            return {
                                'success': False,
                                'status': 'failed',
                                'message': f"Transaction failed: {status_obj['err']}",
                                'transaction_signature': txn_signature
                            }
                        
                        # Check confirmation status
                        conf_status = status_obj.get('confirmationStatus', 'processed')
                        logger.info(f"Transaction status: {conf_status}")
                        
                        if conf_status in ['confirmed', 'finalized']:
                            logger.info(f"Transaction confirmed: {txn_signature}")
                            self.payments[payment_address].status = 'swept_confirmed'
                            return {
                                'success': True,
                                'status': conf_status,
                                'message': f"Transaction {conf_status}",
                                'transaction_signature': txn_signature
                            }
                
                # Wait before checking again
                await asyncio.sleep(confirmation_interval)
            
            # If we get here, we exceeded the confirmation attempts
            logger.warning(f"Transaction {txn_signature} not confirmed after {max_confirmations} attempts")
            
            # Set status to swept anyway since the transaction was submitted
            self.payments[payment_address].status = 'swept_unconfirmed'
            return {
                'success': True,
                'status': 'unconfirmed',
                'message': f"Transaction not confirmed after {max_confirmations} attempts, but was submitted",
                'transaction_signature': txn_signature
            }
            
        except Exception as e:
            logger.error(f"Error in sweep and confirm: {str(e)}")
            return {'success': False, 'message': f"Error confirming sweep: {str(e)}"}

    async def cleanup_expired_payments(self):
        """Check for and remove expired payments."""
        expired_addresses = []
        for address, payment in self.payments.items():
            if payment.is_expired() and payment.status == 'pending':
                payment.status = 'expired'
                expired_addresses.append(address)
                logger.info(f"Payment {address} expired")
        
        # You might want to keep expired payments for record-keeping
        # or remove them to save memory
        return expired_addresses
        
    async def check_transaction_status(self, signature):
        """Check the status of a transaction on the Solana blockchain."""
        try:
            if not signature:
                return {'success': False, 'status': 'invalid', 'message': 'Invalid transaction signature'}
                
            # For mocked/simulated transactions, assume success
            if signature.startswith(('mock_', 'simulated_')):
                return {'success': True, 'status': 'confirmed', 'message': 'Simulated transaction successful'}
            
            # Try checking transaction status first - this is more efficient
            params = [signature, {"commitment": "confirmed"}]
            status_response = make_rpc_request("getSignatureStatuses", [params])
            
            if status_response and 'result' in status_response and 'value' in status_response['result']:
                statuses = status_response['result']['value']
                if statuses and statuses[0] != None:
                    status_obj = statuses[0]
                    if status_obj.get('err'):
                        logger.error(f"Transaction failed with error: {status_obj['err']}")
                        return {'success': False, 'status': 'failed', 'message': f'Transaction failed: {status_obj["err"]}'}
                    elif status_obj.get('confirmationStatus'):
                        conf_status = status_obj['confirmationStatus']
                        logger.info(f"Transaction {signature} status: {conf_status}")
                        
                        if conf_status in ['confirmed', 'finalized']:
                            return {'success': True, 'status': conf_status, 'message': f'Transaction {conf_status}'}
                        else:
                            return {'success': False, 'status': conf_status, 'message': f'Transaction still processing: {conf_status}'}
                    else:
                        # No confirmation status found but no error either - assume it's confirmed
                        return {'success': True, 'status': 'processed', 'message': 'Transaction processed'}
                else:
                    # If no status is found, fall back to getTransaction
                    logger.info(f"No signature status found for {signature}, checking full transaction")
            
            # Use getTransaction as a fallback or for more detailed information
            params = [signature, {"commitment": "confirmed"}]
            response_data = make_rpc_request("getTransaction", params)
            
            # Check for RPC errors related to invalid parameters
            if response_data and 'error' in response_data:
                error = response_data['error']
                if 'Invalid param' in error.get('message', ''):
                    logger.error(f"Invalid transaction signature format: {signature}")
                    return {'success': False, 'status': 'invalid', 'message': 'Invalid transaction signature format'}
                else:
                    logger.error(f"RPC error: {error}")
                    return {'success': False, 'status': 'error', 'message': f"RPC error: {error.get('message', 'Unknown error')}"}
            
            # Process the response
            if response_data and 'result' in response_data:
                # If result is None, transaction was not found
                if response_data['result'] == None:
                    return {'success': False, 'status': 'not_found', 'message': 'Transaction not found'}
                
                # Extract transaction data
                tx_data = response_data['result']
                
                # Check for errors in the transaction
                if 'meta' in tx_data and 'err' in tx_data['meta']:
                    if tx_data['meta']['err']:
                        error_info = tx_data['meta']['err']
                        logger.error(f"Transaction failed with error: {error_info}")
                        return {'success': False, 'status': 'failed', 'message': f'Transaction failed: {error_info}'}
                
                # Check confirmation status
                if 'confirmationStatus' in tx_data:
                    conf_status = tx_data['confirmationStatus']
                    logger.info(f"Transaction {signature} status: {conf_status}")
                    
                    if conf_status in ['confirmed', 'finalized']:
                        return {'success': True, 'status': conf_status, 'message': f'Transaction {conf_status}'}
                    else:
                        return {'success': False, 'status': conf_status, 'message': f'Transaction still processing: {conf_status}'}
                
                # If we have a result but no confirmation status or error, assume it's confirmed
                return {'success': True, 'status': 'confirmed', 'message': 'Transaction confirmed'}
            else:
                return {'success': False, 'status': 'error', 'message': 'Failed to check transaction status'}
        
        except Exception as e:
            logger.error(f"Error checking transaction status: {str(e)}")
            return {'success': False, 'status': 'error', 'message': f'Error checking transaction status: {str(e)}'}
        
    async def verify_token_account_exists(self, token_account_address):
        """Verify if a token account exists on the blockchain."""
        try:
            # Convert address to Pubkey
            token_account_pubkey = str(token_account_address)
            
            # Make RPC call to get account info
            params = [token_account_pubkey, {"encoding": "jsonParsed", "commitment": "confirmed"}]
            response_data = make_rpc_request("getAccountInfo", params)
            
            # Check if account exists
            if response_data and 'result' in response_data:
                result = response_data['result']
                # If value is null, account doesn't exist
                if result['value'] == None:
                    logger.warning(f"Token account {token_account_address} does not exist on chain")
                    return False
                
                # Verify it's a token account
                if 'data' in result['value'] and 'parsed' in result['value']['data']:
                    data = result['value']['data']['parsed']
                    if 'type' in data and data['type'] == 'account':
                        logger.info(f"Verified token account {token_account_address} exists on chain")
                        return True
                
                logger.warning(f"Account {token_account_address} exists but is not a token account")
                return False
            else:
                logger.warning(f"Failed to get account info for {token_account_address}")
                return False
        except Exception as e:
            logger.error(f"Error verifying token account: {str(e)}")
            return False

    async def verify_token_balance(self, token_account_address):
        """Verify the actual token balance in a token account."""
        try:
            # Make RPC call to get account info with jsonParsed encoding
            params = [token_account_address, {"encoding": "jsonParsed", "commitment": "confirmed"}]
            response_data = make_rpc_request("getAccountInfo", params)
            
            if response_data and 'result' in response_data and 'value' in response_data['result']:
                result = response_data['result']['value']
                
                # If value is null, account doesn't exist
                if result == None:
                    logger.warning(f"Token account {token_account_address} does not exist")
                    return 0
                
                # Parse the account data to get token balance
                if 'data' in result and 'parsed' in result['data']:
                    data = result['data']['parsed']
                    if 'info' in data and 'tokenAmount' in data['info']:
                        token_amount = data['info']['tokenAmount']
                        balance = int(token_amount['amount'])
                        decimals = token_amount.get('decimals', 0)
                        display_balance = balance / (10 ** decimals) if decimals > 0 else balance
                        
                        logger.info(f"Token account {token_account_address} has actual balance of {balance} raw units ({display_balance} tokens)")
                        return balance
            
            logger.warning(f"Could not determine balance for token account {token_account_address}")
            return 0
        except Exception as e:
            logger.error(f"Error verifying token balance: {str(e)}")
            return 0

    def _convert_token_units(self, amount, to_raw=True):
        """
        Convert between token units and raw units.
        
        Args:
            amount: The amount to convert
            to_raw: If True, convert from token units to raw units. If False, convert from raw to token units.
            
        Returns:
            The converted amount
        """
        token_decimals = int(os.getenv('SPL_TOKEN_DECIMALS', '9'))
        
        if to_raw:
            # Check if already in raw units (large number)
            if amount >= 10 ** (token_decimals - 1):  # Assume already raw if >= 10^(decimals-1)
                return amount
            else:
                return amount * (10 ** token_decimals)
        else:
            # Convert from raw to token units
            return amount / (10 ** token_decimals)
            
    def _is_raw_units(self, amount):
        """
        Determine if an amount is likely in raw units or token units.
        
        Args:
            amount: The amount to check
            
        Returns:
            True if the amount appears to be in raw units, False otherwise
        """
        token_decimals = int(os.getenv('SPL_TOKEN_DECIMALS', '9'))
        return amount >= 10 ** (token_decimals - 1)

    async def verify_token_account_data(self, token_account_address):
        """Verify that a token account is valid and has correct data structure for transfers."""
        try:
            # Make RPC call to get account info with jsonParsed encoding
            params = [token_account_address, {"encoding": "jsonParsed", "commitment": "confirmed"}]
            response_data = make_rpc_request("getAccountInfo", params)
            
            if response_data and 'result' in response_data and 'value' in response_data['result']:
                result = response_data['result']['value']
                
                # If value is null, account doesn't exist
                if result == None:
                    logger.warning(f"Token account {token_account_address} does not exist")
                    return False, "Account does not exist"
                
                # Parse the account data to verify token account structure
                if 'data' in result and 'parsed' in result['data']:
                    data = result['data']['parsed']
                    # Check if it's a token account
                    if 'type' in data and data['type'] == 'account':
                        info = data.get('info', {})
                        
                        # Check if it's the right mint
                        account_mint = info.get('mint')
                        if account_mint != SPL_TOKEN_MINT:
                            logger.warning(f"Token account {token_account_address} is for mint {account_mint}, not {SPL_TOKEN_MINT}")
                            return False, f"Wrong token mint: {account_mint}"
                        
                        # Check if the token account is owned by the expected address
                        owner = info.get('owner')
                        state = info.get('state')
                        
                        # Check if the account is frozen or closed
                        if state and state != "initialized":
                            logger.warning(f"Token account {token_account_address} state is {state}, not initialized")
                            return False, f"Invalid account state: {state}"
                        
                        # Token account looks valid
                        logger.info(f"Token account {token_account_address} is valid: mint={account_mint}, owner={owner}, state={state}")
                        return True, None
                    else:
                        logger.warning(f"Account {token_account_address} is not a token account")
                        return False, "Not a token account"
                else:
                    logger.warning(f"Account {token_account_address} data is not in expected format")
                    return False, "Invalid account data format"
            else:
                logger.warning(f"Failed to get account info for {token_account_address}")
                return False, "Failed to get account info"
        except Exception as e:
            logger.error(f"Error verifying token account data: {str(e)}")
            return False, str(e)

    async def create_associated_token_account(self, owner_address, mint=None):
        """
        Create an Associated Token Account (ATA) for a given wallet address and token mint.
        
        Args:
            owner_address: The wallet address that will own the token account
            mint: The mint address of the token (defaults to SPL_TOKEN_MINT)
            
        Returns:
            dict: Result with status and token account address
        """
        if mint is None:
            mint = SPL_TOKEN_MINT
            
        if not mint:
            return {'success': False, 'message': 'Token mint address not provided'}
            
        try:
            # Create main wallet keypair for fee payment
            try:
                logger.info("Parsing main wallet private key for ATA creation")
                
                # Try different formats for wallet private keys
                keypair = None
                error_messages = []
                
                # 1. Try as array of bytes (Uint8Array)
                if MAIN_WALLET_PRIVATE_KEY.startswith('[') and MAIN_WALLET_PRIVATE_KEY.endswith(']'):
                    try:
                        import json
                        private_key_array = json.loads(MAIN_WALLET_PRIVATE_KEY)
                        private_key_bytes = bytes(private_key_array)
                        keypair = Keypair.from_bytes(private_key_bytes)
                    except Exception as e:
                        error_messages.append(f"Array format failed: {str(e)}")
                
                # 2. Try as base58 string (common export format)
                if not keypair:
                    try:
                        private_key_bytes = b58decode(MAIN_WALLET_PRIVATE_KEY)
                        keypair = Keypair.from_bytes(private_key_bytes)
                    except Exception as e:
                        error_messages.append(f"Base58 decode failed: {str(e)}")
                
                # 3. Try as hex string
                if not keypair:
                    try:
                        private_key_bytes = bytes.fromhex(MAIN_WALLET_PRIVATE_KEY)
                        keypair = Keypair.from_bytes(private_key_bytes)
                    except Exception as e:
                        error_messages.append(f"Hex decode failed: {str(e)}")
                
                # If we have a keypair, use it
                if keypair:
                    main_wallet_keypair = keypair
                else:
                    # Log all errors and raise exception
                    logger.error(f"Failed to parse private key: {'; '.join(error_messages)}")
                    raise ValueError(f"Could not parse private key in any format: {'; '.join(error_messages)}")
                
                # Verify the public key matches what we expect
                derived_pubkey = str(main_wallet_keypair.pubkey())
                if derived_pubkey != MAIN_WALLET_ADDRESS:
                    logger.warning(f"Derived public key {derived_pubkey} doesn't match expected wallet address {MAIN_WALLET_ADDRESS}")
            
            except Exception as e:
                logger.error(f"Error parsing private key for ATA creation: {str(e)}")
                return {'success': False, 'message': f'Error parsing private key: {str(e)}'}
            
            # Get recent blockhash
            blockhash_resp = make_rpc_request("getLatestBlockhash", [{"commitment": "finalized"}])
            if not blockhash_resp or 'result' not in blockhash_resp or 'value' not in blockhash_resp['result']:
                return {'success': False, 'message': 'Failed to get blockhash for ATA creation'}
            
            blockhash_str = blockhash_resp['result']['value']['blockhash']
            blockhash_bytes = b58decode(blockhash_str)
            blockhash = Hash(blockhash_bytes)
            
            # Convert addresses to Pubkey objects
            owner_pubkey = Pubkey.from_string(owner_address)
            mint_pubkey = Pubkey.from_string(mint)
            fee_payer = main_wallet_keypair.pubkey()
            
            # Get the ATA address (deterministic based on owner and mint)
            # Note: This is a simplified approach - would need spl-token library for proper implementation
            # In production, use the spl-token library or a direct RPC call to findAssociatedTokenAddress
            
            # For now, just return a placeholder
            logger.info(f"ATA creation not implemented - would create ATA for owner {owner_address}, mint {mint}")
            
            if TESTING_MODE:
                return {
                    'success': True,
                    'message': 'Simulated ATA creation in testing mode',
                    'token_account': f"simulated_ata_{owner_address}_{int(time.time())}",
                    'mock': True
                }
            else:
                return {
                    'success': False,
                    'message': 'ATA creation not fully implemented yet',
                    'error_type': 'not_implemented'
                }
                
        except Exception as e:
            logger.error(f"Error creating ATA: {str(e)}")
            return {'success': False, 'message': f'Error creating ATA: {str(e)}'}
            
    async def get_or_create_token_account(self, owner_address, mint=None):
        """
        Get an existing valid token account or create one if needed.
        
        Args:
            owner_address: The wallet address that owns the token account
            mint: The mint address of the token (defaults to SPL_TOKEN_MINT)
            
        Returns:
            dict: Result with status and token account address
        """
        if mint is None:
            mint = SPL_TOKEN_MINT
            
        try:
            # First, try to find existing token accounts for this owner and mint
            payment_pubkey = Pubkey.from_string(owner_address)
            mint_pubkey = Pubkey.from_string(mint)
            
            params = [
                str(payment_pubkey),
                {"mint": str(mint_pubkey)},
                {"encoding": "jsonParsed", "commitment": "confirmed"}
            ]
            
            response_data = make_rpc_request("getTokenAccountsByOwner", params)
            
            if response_data and 'result' in response_data and 'value' in response_data['result']:
                token_accounts = response_data['result']['value']
                logger.info(f"Found {len(token_accounts)} token accounts for owner {owner_address}")
                
                # Check each account to see if it's valid
                for account in token_accounts:
                    token_account_address = account['pubkey']
                    is_valid, error = await self.verify_token_account_data(token_account_address)
                    
                    if is_valid:
                        logger.info(f"Found valid token account {token_account_address} for owner {owner_address}")
                        return {
                            'success': True,
                            'message': 'Found existing valid token account',
                            'token_account': token_account_address,
                            'newly_created': False
                        }
            
            # If we get here, we either didn't find any accounts or none were valid
            logger.info(f"No valid token accounts found for owner {owner_address}, will create a new one")
            
            # Create a new ATA
            create_result = await self.create_associated_token_account(owner_address, mint)
            if create_result['success']:
                return {
                    'success': True,
                    'message': 'Created new token account',
                    'token_account': create_result['token_account'],
                    'newly_created': True
                }
            else:
                return create_result
                
        except Exception as e:
            logger.error(f"Error getting or creating token account: {str(e)}")
            return {'success': False, 'message': f'Error getting or creating token account: {str(e)}'}

    async def verify_token_account_authority(self, token_account_address, owner_address):
        """
        Verify that an owner address has authority over a token account.
        
        Args:
            token_account_address: The token account address to check
            owner_address: The wallet address that should own the token account
            
        Returns:
            tuple: (is_authorized, error_message)
        """
        try:
            # Make RPC call to get account info with jsonParsed encoding
            params = [token_account_address, {"encoding": "jsonParsed", "commitment": "confirmed"}]
            response_data = make_rpc_request("getAccountInfo", params)
            
            if response_data and 'result' in response_data and 'value' in response_data['result']:
                result = response_data['result']['value']
                
                # If value is null, account doesn't exist
                if result == None:
                    return False, "Account does not exist"
                
                # Parse the account data
                if 'data' in result and 'parsed' in result['data']:
                    data = result['data']['parsed']
                    
                    # Check if it's a token account
                    if 'type' in data and data['type'] == 'account':
                        info = data.get('info', {})
                        
                        # Check if the token account is owned by the expected address
                        account_owner = info.get('owner')
                        if account_owner != owner_address:
                            logger.warning(f"Token account {token_account_address} is owned by {account_owner}, not {owner_address}")
                            return False, f"Token account is owned by {account_owner}, not {owner_address}"
                        
                        # Check if the account is frozen
                        state = info.get('state')
                        if state == "frozen":
                            logger.warning(f"Token account {token_account_address} is frozen")
                            return False, "Token account is frozen"
                        
                        # Check if there are any delegate authorities
                        delegate = info.get('delegate')
                        if delegate:
                            logger.info(f"Token account {token_account_address} has delegate {delegate}")
                            # Delegation doesn't necessarily mean the owner can't spend, but it's worth noting
                        
                        # Owner has authority
                        return True, None
                    else:
                        return False, "Not a token account"
                else:
                    return False, "Invalid account data format"
            else:
                return False, "Failed to get account info"
        except Exception as e:
            logger.error(f"Error verifying token account authority: {str(e)}")
            return False, str(e)

    async def get_valid_blockhash(self, commitment="finalized", retries=3, retry_delay=1):
        """Get a valid blockhash and verify it's accepted by the network."""
        for attempt in range(retries):
            try:
                # Get the latest blockhash
                blockhash_resp = make_rpc_request("getLatestBlockhash", [{"commitment": commitment}])
                if blockhash_resp and 'result' in blockhash_resp and 'value' in blockhash_resp['result']:
                    blockhash = blockhash_resp['result']['value']['blockhash']
                    logger.info(f"Got blockhash: {blockhash} (attempt {attempt+1})")
                    
                    # Verify the blockhash is valid by testing it
                    # The isBlockhashValid method expects the blockhash as a string, not a map
                    verify_params = [blockhash]
                    verify_resp = make_rpc_request("isBlockhashValid", verify_params)
                    
                    if verify_resp and 'result' in verify_resp and 'value' in verify_resp['result']:
                        is_valid = verify_resp['result']['value']
                        if is_valid:
                            logger.info(f"Blockhash {blockhash} verified as valid")
                            return blockhash
                        else:
                            logger.warning(f"Blockhash {blockhash} is not valid, retrying...")
                    else:
                        # If verification failed but we have a blockhash, proceed anyway
                        logger.warning(f"Could not verify blockhash validity, but will use it anyway: {blockhash}")
                        return blockhash
                
                # If we couldn't verify or it's not valid, wait before retrying
                if attempt < retries - 1:
                    await asyncio.sleep(retry_delay)
            except Exception as e:
                logger.error(f"Error getting valid blockhash: {str(e)}")
                if attempt < retries - 1:
                    await asyncio.sleep(retry_delay)
        
        # If we get here, we couldn't get a valid blockhash
        logger.error("Failed to get valid blockhash after multiple attempts")
        return None

    async def get_blockhash_simple(self, commitment="confirmed"):
        """Simple method to get a blockhash without validation."""
        try:
            # Use commitment=processed for less delay to ensure blockhash is usable
            if SOLANA_NETWORK == 'mainnet-beta':
                commitment = "processed"
            
            # Get the latest blockhash with specified commitment level
            blockhash_resp = make_rpc_request("getLatestBlockhash", [{"commitment": commitment}])
            if blockhash_resp and 'result' in blockhash_resp and 'value' in blockhash_resp['result']:
                blockhash = blockhash_resp['result']['value']['blockhash']
                logger.info(f"Got blockhash with {commitment} commitment: {blockhash}")
                
                # For mainnet-beta, get the last valid block height for this blockhash
                # This helps ensure we're using a valid blockhash by checking against the current block height
                if SOLANA_NETWORK == 'mainnet-beta' and 'lastValidBlockHeight' in blockhash_resp['result']['value']:
                    last_valid = blockhash_resp['result']['value']['lastValidBlockHeight']
                    logger.info(f"Blockhash valid until block height: {last_valid}")
                    
                    # Get current block height
                    current_block_resp = make_rpc_request("getBlockHeight", [{"commitment": commitment}])
                    if current_block_resp and 'result' in current_block_resp:
                        current_height = current_block_resp['result']
                        logger.info(f"Current block height: {current_height}")
                        
                        # Check if the blockhash is still valid
                        if current_height <= last_valid:
                            return blockhash
                        else:
                            logger.warning(f"Blockhash already expired: current height {current_height} > last valid {last_valid}")
                            return None
                
                # For other networks or if last valid check wasn't performed, just return the blockhash
                return blockhash
            
            return None
        except Exception as e:
            logger.error(f"Error getting simple blockhash: {str(e)}")
            return None

# Create a singleton instance
payment_manager = PaymentManager()

# Function to get the payment manager
def get_payment_manager():
    return payment_manager 