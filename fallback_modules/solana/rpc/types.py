"""
Fallback implementation of solana.rpc.types module
"""
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

class TxOpts:
    """Mock implementation of TxOpts"""
    def __init__(self, 
                 skip_preflight: bool = False, 
                 preflight_commitment: Optional[str] = None,
                 max_retries: Optional[int] = None,
                 **kwargs):
        self.skip_preflight = skip_preflight
        self.preflight_commitment = preflight_commitment
        self.max_retries = max_retries
        self.kwargs = kwargs
        logger.debug(f"Created mock TxOpts: skip_preflight={skip_preflight}, preflight_commitment={preflight_commitment}")
    
    def to_dict(self) -> Dict:
        """Convert options to dictionary for RPC"""
        result = {}
        if self.skip_preflight:
            result["skipPreflight"] = True
        if self.preflight_commitment:
            result["preflightCommitment"] = self.preflight_commitment
        if self.max_retries is not None:
            result["maxRetries"] = self.max_retries
        # Add any other kwargs
        result.update(self.kwargs)
        return result 