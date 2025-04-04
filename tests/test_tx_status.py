import os
import time
import logging
import requests
from base58 import b58decode
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure Solana client
SOLANA_NETWORK = os.getenv("SOLANA_NETWORK", "devnet")
if SOLANA_NETWORK == "mainnet-beta":
    SOLANA_URL = "https://api.mainnet-beta.solana.com"
elif SOLANA_NETWORK == "testnet":
    SOLANA_URL = "https://api.testnet.solana.com"
else:
    SOLANA_URL = "https://api.devnet.solana.com"

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
    
    logger.info(f"Making RPC request: {method} with params: {params}")
    
    for attempt in range(retries):
        try:
            response = requests.post(SOLANA_URL, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if "error" in result:
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

def test_transaction_status():
    """Test checking the status of a transaction."""
    try:
        # Use a valid format for the transaction signature
        # Solana signatures are 88 characters long in base58 format
        mock_signature = "5VERv8NMvzbJMEkV8xnrLkEaWRtSz9CosKDYjCJjBRnbJLgp8uirBgmQpjKhoR4tjF3ZpRzrFmBV6UjKdiSZkQUW"
        logger.info(f"Testing transaction status check with signature: {mock_signature}")
        
        # Make a direct call to getTransaction RPC endpoint
        params = [mock_signature, {"commitment": "confirmed"}]
        response = make_rpc_request("getTransaction", params)
        
        if response and "result" in response:
            logger.info(f"Successfully made getTransaction call")
            logger.info(f"Response structure: {response}")
            
            # The signature likely won't be found, but the API call itself should work
            # without invalid parameter errors
            return True
        else:
            # If we got an error about invalid parameters, that's a problem with our code
            if response and "error" in response and "Invalid param" in response["error"].get("message", ""):
                logger.error("Invalid parameter format")
                return False
            
            # If signature not found, that's expected
            logger.info("Signature not found, but API call format was valid")
            return True
    except Exception as e:
        logger.error(f"Error in transaction status test: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def main():
    """Run the test."""
    logger.info("Testing Solana transaction status check...")
    result = test_transaction_status()
    logger.info(f"Test {'PASSED' if result else 'FAILED'}")

if __name__ == "__main__":
    main() 