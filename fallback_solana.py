"""
Fallback solana module stub for when the real solana package can't be installed.
This provides minimal functionality required by solana_payments.py.
"""

import logging
logger = logging.getLogger(__name__)

logger.warning("Using fallback solana module! This is a minimal implementation and not all features will work.")

# Version for logging
__version__ = "0.31.0-fallback"

class rpc:
    class api:
        class Client:
            def __init__(self, endpoint_url):
                self.endpoint_url = endpoint_url
                logger.warning(f"Created fallback solana Client with endpoint: {endpoint_url}")

            def get_balance(self, pubkey):
                logger.warning("Fallback solana: get_balance called but not implemented")
                return {"result": {"value": 0}}

    class commitment:
        class Commitment:
            def __init__(self, value):
                self.value = value

    class types:
        class TxOpts:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

class transaction:
    class Transaction:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def add(self, instruction):
            pass

        def sign(self, *signers):
            pass

        def serialize(self):
            return b''

# Add other necessary classes as minimal stubs
