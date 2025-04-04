"""
Fallback solana module stub for when the real solana package can't be installed.
This provides minimal functionality required by solana_payments.py.
"""

import logging
import base64
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

logger.warning("Using fallback solana module! This is a minimal implementation and not all features will work.")

# Version for logging
__version__ = "0.31.0-fallback"

# Create stub classes needed by solana_payments.py
class MockObject:
    """Base class for mock objects that logs method calls"""
    def __getattr__(self, name):
        def method(*args, **kwargs):
            logger.warning(f"Called undefined method {name} on {self.__class__.__name__}")
            return None
        return method

class Pubkey(MockObject):
    def __init__(self, address=None):
        self.address = address or "mock_pubkey_address"
    
    def __str__(self):
        return self.address
        
    @classmethod
    def from_string(cls, address_str):
        return cls(address_str)
        
    def to_base58(self):
        return self.address.encode()

class Keypair(MockObject):
    def __init__(self):
        self._pubkey = Pubkey()
        self.secret_key = bytes([0] * 32)  # Mock 32 bytes
    
    def pubkey(self):
        return self._pubkey
        
    @classmethod
    def from_bytes(cls, byte_data):
        return cls()
        
    @classmethod
    def from_secret_key(cls, secret_key):
        return cls()

class Instruction(MockObject):
    def __init__(self, program_id=None, accounts=None, data=None):
        self.program_id = program_id
        self.accounts = accounts or []
        self.data = data or b''

class AccountMeta(MockObject):
    def __init__(self, pubkey=None, is_signer=False, is_writable=False):
        self.pubkey = pubkey
        self.is_signer = is_signer
        self.is_writable = is_writable

class Hash(MockObject):
    def __init__(self, hash_bytes=None):
        self.hash_bytes = hash_bytes or bytes([0] * 32)

class SystemProgram(MockObject):
    """Mock system program classes"""
    @staticmethod
    def transfer(from_pubkey, to_pubkey, lamports):
        logger.warning("Mock system_program transfer called")
        return Instruction()

# Create module-level functions that are called directly
def transfer(params):
    logger.warning("Mock transfer function called")
    return Instruction() 