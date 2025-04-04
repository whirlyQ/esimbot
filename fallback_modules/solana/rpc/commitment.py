"""
Fallback implementation of solana.rpc.commitment module
"""
import logging

logger = logging.getLogger(__name__)

class Commitment:
    """Mock implementation of Commitment enum"""
    FINALIZED = "finalized"
    CONFIRMED = "confirmed"
    PROCESSED = "processed"
    
    def __init__(self, value):
        self.value = value
        valid_values = [self.FINALIZED, self.CONFIRMED, self.PROCESSED]
        if value not in valid_values:
            logger.warning(f"Invalid commitment value: {value}, valid values are {valid_values}")
    
    def __str__(self):
        return self.value 