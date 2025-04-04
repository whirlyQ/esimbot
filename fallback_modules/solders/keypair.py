"""
Fallback implementation of solders.keypair module
"""
import logging
import base58
import os
from . import pubkey 

logger = logging.getLogger(__name__)

class Keypair:
    """Mock implementation of Keypair class"""
    def __init__(self, secret_key=None):
        # Either use provided secret key or generate 32 random bytes
        self.secret_key = secret_key or os.urandom(32)
        self._pubkey = pubkey.Pubkey(address=f"Mock{base58.b58encode(self.secret_key[:8]).decode()}")
        logger.debug(f"Created mock Keypair with pubkey: {self._pubkey}")
    
    def pubkey(self):
        """Get the public key for this keypair"""
        return self._pubkey
    
    @classmethod
    def from_bytes(cls, byte_data):
        """Create a Keypair from bytes"""
        return cls(secret_key=byte_data)
    
    @classmethod
    def from_secret_key(cls, secret_key):
        """Create a Keypair from a secret key"""
        return cls(secret_key=secret_key)
    
    @classmethod
    def generate(cls):
        """Generate a new random keypair"""
        return cls() 