"""
Fallback implementation of solders.pubkey module
"""
import logging
import base64
import base58

logger = logging.getLogger(__name__)

class Pubkey:
    """Mock implementation of Pubkey class"""
    def __init__(self, pubkey_bytes=None, address=None):
        if address:
            self.address = address
        elif pubkey_bytes:
            # Convert bytes to address string
            self.address = base58.b58encode(pubkey_bytes).decode()
        else:
            # Create a default address that's recognizable
            self.address = "Mock11111111111111111111111111111111111111111"
        
        logger.debug(f"Created mock Pubkey: {self.address}")
    
    def __str__(self):
        return self.address
    
    def __eq__(self, other):
        if isinstance(other, Pubkey):
            return self.address == other.address
        return False
    
    @classmethod
    def from_string(cls, address_str):
        """Create a Pubkey from an address string"""
        return cls(address=address_str)
    
    def to_base58(self):
        """Convert to base58 bytes"""
        try:
            return base58.b58encode(base58.b58decode(self.address))
        except:
            # If we can't decode the address, just encode the string itself
            return self.address.encode() 