"""
Fallback implementation of solders.hash module
"""
import logging
import base58

logger = logging.getLogger(__name__)

class Hash:
    """Mock implementation of Hash class"""
    def __init__(self, hash_bytes=None):
        if hash_bytes:
            self.hash_bytes = hash_bytes
            self.hash_str = base58.b58encode(hash_bytes).decode()
        else:
            # Create a default recognizable blockhash
            self.hash_str = "MockHashXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
            self.hash_bytes = base58.b58decode(self.hash_str)
        
        logger.debug(f"Created mock Hash: {self.hash_str}")
    
    def __str__(self):
        return self.hash_str
    
    @classmethod
    def from_string(cls, hash_str):
        """Create a Hash from a string"""
        hash_bytes = base58.b58decode(hash_str)
        return cls(hash_bytes=hash_bytes) 