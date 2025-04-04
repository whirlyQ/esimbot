"""
Fallback implementation of solana.rpc.api module
"""
import logging
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)

class Client:
    """
    Mock implementation of Solana RPC Client
    """
    def __init__(self, endpoint_url: str, timeout: Optional[int] = None):
        self.endpoint_url = endpoint_url
        self.timeout = timeout
        logger.warning(f"Created fallback Solana RPC Client with endpoint: {endpoint_url}")
        
    def get_balance(self, pubkey: Any, **kwargs) -> Dict:
        """Mocked implementation of get_balance"""
        logger.warning(f"Mock get_balance called for {pubkey}")
        return {"jsonrpc": "2.0", "id": 1, "result": {"value": 0}}
    
    def get_account_info(self, pubkey: Any, **kwargs) -> Dict:
        """Mocked implementation of get_account_info"""
        logger.warning(f"Mock get_account_info called for {pubkey}")
        return {"jsonrpc": "2.0", "id": 1, "result": None}
    
    def get_token_accounts_by_owner(self, owner: Any, filter_opts: Dict, **kwargs) -> Dict:
        """Mocked implementation of get_token_accounts_by_owner"""
        logger.warning(f"Mock get_token_accounts_by_owner called for {owner}")
        return {"jsonrpc": "2.0", "id": 1, "result": {"value": []}}
    
    def get_latest_blockhash(self, **kwargs) -> Dict:
        """Mocked implementation of get_latest_blockhash"""
        logger.warning("Mock get_latest_blockhash called")
        return {
            "jsonrpc": "2.0", 
            "id": 1, 
            "result": {
                "value": {
                    "blockhash": "11111111111111111111111111111111",
                    "lastValidBlockHeight": 1000000
                }
            }
        }
    
    def is_blockhash_valid(self, blockhash: str, **kwargs) -> Dict:
        """Mocked implementation of is_blockhash_valid"""
        logger.warning(f"Mock is_blockhash_valid called for {blockhash}")
        return {"jsonrpc": "2.0", "id": 1, "result": {"value": True}}
    
    def send_transaction(self, transaction: Any, **kwargs) -> Dict:
        """Mocked implementation of send_transaction"""
        logger.warning("Mock send_transaction called")
        # Use a recognizable fake transaction ID
        return {"jsonrpc": "2.0", "id": 1, "result": "MOCK_TRANSACTION_ID_1234567890"}
    
    def get_transaction(self, tx_sig: str, **kwargs) -> Dict:
        """Mocked implementation of get_transaction"""
        logger.warning(f"Mock get_transaction called for {tx_sig}")
        if tx_sig.startswith("MOCK_"):
            # It's our mock transaction, say it succeeded
            return {
                "jsonrpc": "2.0", 
                "id": 1, 
                "result": {
                    "meta": {"err": None},
                    "confirmationStatus": "confirmed"
                }
            }
        return {"jsonrpc": "2.0", "id": 1, "result": None} 