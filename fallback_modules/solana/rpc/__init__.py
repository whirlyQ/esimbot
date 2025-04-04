"""
Fallback implementation of solana.rpc module
"""
import logging

logger = logging.getLogger(__name__)

# Common RPC responses
DEFAULT_RESPONSE = {"jsonrpc": "2.0", "id": 1, "result": {"value": None}} 