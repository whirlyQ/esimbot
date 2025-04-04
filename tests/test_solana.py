import os
import time
import logging
from base58 import b58decode
from solana.transaction import Transaction
from solders.hash import Hash
from solders.keypair import Keypair
from solders.instruction import Instruction, AccountMeta
from solders.pubkey import Pubkey
from solana.rpc.api import Client
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Constants
SOLANA_NETWORK = os.getenv('SOLANA_NETWORK', 'devnet')
MAIN_WALLET_PRIVATE_KEY = os.getenv('SOLANA_MAIN_WALLET_PRIVATE_KEY')
MAIN_WALLET_ADDRESS = os.getenv('SOLANA_MAIN_WALLET')
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

# Configure Solana client
if SOLANA_NETWORK == 'mainnet-beta':
    SOLANA_URL = 'https://api.mainnet-beta.solana.com'
elif SOLANA_NETWORK == 'testnet':
    SOLANA_URL = 'https://api.testnet.solana.com'
else:
    SOLANA_URL = 'https://api.devnet.solana.com'

solana_client = Client(SOLANA_URL)

def make_rpc_request(method, params=None, retries=3, retry_delay=1):
    """Make a direct JSON-RPC request to the Solana node with retries."""
    if params is None:
        params = []
    
    import requests
    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }
    
    logger.info(f"Making RPC request: {method}")
    
    for attempt in range(retries):
        try:
            response = requests.post(SOLANA_URL, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if 'error' in result:
                    logger.error(f"RPC error: {result['error']}")
                    return None
                logger.info(f"RPC response received for {method}")
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

def test_blockhash():
    """Test getting a blockhash and creating a transaction."""
    try:
        # Get a recent blockhash
        blockhash_resp = make_rpc_request("getLatestBlockhash", [{"commitment": "finalized"}])
        if blockhash_resp and 'result' in blockhash_resp and 'value' in blockhash_resp['result']:
            blockhash_str = blockhash_resp['result']['value']['blockhash']
            logger.info(f"Got blockhash: {blockhash_str}")
            
            # Convert from base58 to Hash object
            from solders.hash import Hash
            from base58 import b58decode
            
            try:
                # The blockhash is in base58 format, not hex
                blockhash_bytes = b58decode(blockhash_str)
                logger.info(f"Decoded blockhash from base58 - length: {len(blockhash_bytes)} bytes")
                
                # Create Hash object from bytes
                blockhash = Hash(blockhash_bytes)
                logger.info(f"Created Hash object from blockhash")
                
                # Create a transaction with the blockhash
                tx = Transaction(
                    fee_payer=Pubkey.from_string("11111111111111111111111111111111"),  # Dummy address
                    recent_blockhash=blockhash
                )
                logger.info(f"Successfully created transaction with blockhash")
                
                return True
            except Exception as e:
                logger.error(f"Error converting blockhash: {str(e)}")
                import traceback
                logger.error(f"Conversion traceback: {traceback.format_exc()}")
                return False
        else:
            logger.error("Failed to get blockhash")
            return False
    except Exception as e:
        logger.error(f"Error in blockhash test: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def test_keypair():
    """Test loading a keypair from a private key."""
    try:
        if not MAIN_WALLET_PRIVATE_KEY:
            logger.error("MAIN_WALLET_PRIVATE_KEY not set in environment")
            return False
        
        # Print information about the key format
        logger.info(f"Private key first 10 chars: {MAIN_WALLET_PRIVATE_KEY[:10]}...")
        logger.info(f"Private key length: {len(MAIN_WALLET_PRIVATE_KEY)} characters")
        
        # Check if it's an array format
        if MAIN_WALLET_PRIVATE_KEY.startswith('[') and MAIN_WALLET_PRIVATE_KEY.endswith(']'):
            logger.info("Key appears to be in array format")
            try:
                import json
                private_key_array = json.loads(MAIN_WALLET_PRIVATE_KEY)
                logger.info(f"Successfully parsed key as JSON array with {len(private_key_array)} elements")
                
                private_key_bytes = bytes(private_key_array)
                keypair = Keypair.from_bytes(private_key_bytes)
                logger.info(f"Created keypair from array private key")
                
                pubkey = keypair.pubkey()
                logger.info(f"Derived public key: {pubkey}")
                
                if MAIN_WALLET_ADDRESS and str(pubkey) != MAIN_WALLET_ADDRESS:
                    logger.warning(f"Derived public key {pubkey} doesn't match expected wallet address {MAIN_WALLET_ADDRESS}")
                
                return True
            except Exception as e:
                logger.error(f"Error parsing array format: {str(e)}")
        
        # Try it as a hex string
        try:
            logger.info("Attempting to parse as hex string")
            if MAIN_WALLET_PRIVATE_KEY.startswith("0x"):
                hex_key = MAIN_WALLET_PRIVATE_KEY[2:]
            else:
                hex_key = MAIN_WALLET_PRIVATE_KEY
                
            private_key_bytes = bytes.fromhex(hex_key)
            logger.info(f"Successfully parsed key as hex - length: {len(private_key_bytes)} bytes")
            
            keypair = Keypair.from_bytes(private_key_bytes)
            logger.info(f"Created keypair from hex private key")
            
            pubkey = keypair.pubkey()
            logger.info(f"Derived public key: {pubkey}")
            
            if MAIN_WALLET_ADDRESS and str(pubkey) != MAIN_WALLET_ADDRESS:
                logger.warning(f"Derived public key {pubkey} doesn't match expected wallet address {MAIN_WALLET_ADDRESS}")
            
            return True
        except Exception as e:
            logger.error(f"Error parsing as hex: {str(e)}")
        
        # Try various base58 conversions
        try:
            logger.info("Attempting to parse as base58 string")
            try:
                private_key_bytes = b58decode(MAIN_WALLET_PRIVATE_KEY)
                logger.info(f"Successfully parsed key as base58 - length: {len(private_key_bytes)} bytes")
            except ValueError as e:
                logger.error(f"Base58 decode failed: {str(e)}")
                return False
            
            keypair = Keypair.from_bytes(private_key_bytes)
            logger.info(f"Created keypair from base58 private key")
            
            pubkey = keypair.pubkey()
            logger.info(f"Derived public key: {pubkey}")
            
            if MAIN_WALLET_ADDRESS and str(pubkey) != MAIN_WALLET_ADDRESS:
                logger.warning(f"Derived public key {pubkey} doesn't match expected wallet address {MAIN_WALLET_ADDRESS}")
            
            return True
        except Exception as e:
            logger.error(f"Error in keypair creation: {str(e)}")
            
        logger.error("Failed to parse private key in any supported format")
        return False
    except Exception as e:
        logger.error(f"Error in keypair test: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def test_transaction_status():
    """Test checking the status of a transaction."""
    try:
        # Create a mock transaction signature
        mock_signature = f"mock_test_tx_{int(time.time())}"
        logger.info(f"Testing transaction status check with mock signature: {mock_signature}")
        
        # Make a direct call to getSignatureStatuses RPC endpoint
        # In a real scenario, this would be a valid signature
        # The signature should be passed as an array element
        params = [[mock_signature], {"commitment": "confirmed"}]
        response = make_rpc_request("getSignatureStatuses", params)
        
        if response and 'result' in response:
            logger.info(f"Successfully made getSignatureStatuses call")
            logger.info(f"Result structure: {response['result']}")
            
            # The mock signature won't be found, but the call itself worked
            if 'value' in response['result'] and response['result']['value'] == [None]:
                logger.info("Mock signature not found as expected")
                return True
            else:
                logger.error("Unexpected response format")
                return False
        else:
            logger.error("Failed to get transaction status")
            return False
    except Exception as e:
        logger.error(f"Error in transaction status test: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def main():
    """Run all tests."""
    logger.info("Starting Solana integration tests...")
    
    # Test keypair loading
    logger.info("\n=== Testing Keypair Loading ===")
    keypair_result = test_keypair()
    logger.info(f"Keypair test {'PASSED' if keypair_result else 'FAILED'}")
    
    # Test blockhash and transaction
    logger.info("\n=== Testing Blockhash and Transaction ===")
    blockhash_result = test_blockhash()
    logger.info(f"Blockhash test {'PASSED' if blockhash_result else 'FAILED'}")
    
    # Test transaction status check
    logger.info("\n=== Testing Transaction Status Check ===")
    tx_status_result = test_transaction_status()
    logger.info(f"Transaction status test {'PASSED' if tx_status_result else 'FAILED'}")
    
    # Overall result
    logger.info("\n=== Test Results ===")
    if keypair_result and blockhash_result and tx_status_result:
        logger.info("All tests PASSED!")
    else:
        logger.error("Some tests FAILED!")

if __name__ == "__main__":
    main() 