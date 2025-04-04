"""
Fallback implementation of solana.transaction module
"""
import logging
import base64
from typing import Any, List, Optional, Union

logger = logging.getLogger(__name__)

class Transaction:
    """Mock implementation of Transaction class"""
    def __init__(self, fee_payer=None, recent_blockhash=None):
        self.fee_payer = fee_payer
        self.recent_blockhash = recent_blockhash
        self.instructions = []
        self.signatures = []
        logger.debug(f"Created mock Transaction with fee_payer={fee_payer}, recent_blockhash={recent_blockhash}")
    
    def add(self, instruction):
        """Add an instruction to the transaction"""
        self.instructions.append(instruction)
        logger.debug(f"Added instruction to transaction, total: {len(self.instructions)}")
        return self
    
    def sign(self, *signers):
        """Sign the transaction with the given signers"""
        self.signatures.extend([signer.pubkey() for signer in signers])
        logger.debug(f"Transaction signed with {len(signers)} signers")
        return self
    
    def serialize(self):
        """Serialize the transaction to bytes"""
        # Create a recognizable mock transaction
        mock_data = b'MOCK_TRANSACTION_' + base64.b64encode(str(id(self)).encode())
        logger.debug(f"Serialized mock transaction to {len(mock_data)} bytes")
        return mock_data 