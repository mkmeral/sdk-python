"""Backwards compatibility for mcp_types module.

DEPRECATED: Import from strands.mcp.mcp_types instead of strands.tools.mcp.mcp_types
"""

import warnings

from ...mcp.mcp_types import MCPToolResult, MCPTransport

warnings.warn(
    "Importing from 'strands.tools.mcp.mcp_types' is deprecated. "
    "Use 'strands.mcp' or 'strands.mcp.mcp_types' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["MCPTransport", "MCPToolResult"]
