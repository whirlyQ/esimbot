"""
Fallback implementation of solders.instruction module
"""
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

class AccountMeta:
    """Mock implementation of AccountMeta class"""
    def __init__(self, pubkey, is_signer=False, is_writable=False):
        self.pubkey = pubkey
        self.is_signer = is_signer
        self.is_writable = is_writable
        logger.debug(f"Created mock AccountMeta: pubkey={pubkey}, is_signer={is_signer}, is_writable={is_writable}")

class Instruction:
    """Mock implementation of Instruction class"""
    def __init__(self, program_id, accounts=None, data=None):
        self.program_id = program_id
        self.accounts = accounts or []
        self.data = data or b''
        logger.debug(f"Created mock Instruction: program_id={program_id}, accounts={len(self.accounts) if accounts else 0}, data_len={len(self.data) if data else 0}") 