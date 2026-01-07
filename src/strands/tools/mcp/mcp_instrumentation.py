"""Backwards compatibility for mcp_instrumentation module.

DEPRECATED: Import from strands.mcp.mcp_instrumentation instead of strands.tools.mcp.mcp_instrumentation
"""

import warnings

from ...mcp.mcp_instrumentation import mcp_instrumentation

warnings.warn(
    "Importing from 'strands.tools.mcp.mcp_instrumentation' is deprecated. "
    "Use 'strands.mcp.mcp_instrumentation' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["mcp_instrumentation"]
