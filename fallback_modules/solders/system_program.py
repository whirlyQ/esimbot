"""
Fallback implementation of solders.system_program module
"""
import logging
from .instruction import Instruction, AccountMeta

logger = logging.getLogger(__name__)

class TransferParams:
    """Mock implementation of TransferParams class"""
    def __init__(self, from_pubkey, to_pubkey, lamports):
        self.from_pubkey = from_pubkey
        self.to_pubkey = to_pubkey
        self.lamports = lamports
        logger.debug(f"Created mock TransferParams: from={from_pubkey}, to={to_pubkey}, lamports={lamports}")

def transfer(params):
    """Mock implementation of transfer function"""
    logger.info(f"Mock system_program.transfer called: {params.lamports} lamports from {params.from_pubkey} to {params.to_pubkey}")
    
    # System program ID (hardcoded as in real Solana)
    system_program_id = "11111111111111111111111111111111"
    
    # Create account metas
    accounts = [
        AccountMeta(pubkey=params.from_pubkey, is_signer=True, is_writable=True),
        AccountMeta(pubkey=params.to_pubkey, is_signer=False, is_writable=True)
    ]
    
    # Create data (in real implementation this would be properly encoded)
    # Just using a placeholder here
    data = b'MOCK_TRANSFER_INSTRUCTION'
    
    # Return instruction
    return Instruction(program_id=system_program_id, accounts=accounts, data=data) 