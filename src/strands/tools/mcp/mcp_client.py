"""Backwards compatibility for mcp_client module.

DEPRECATED: Import from strands.mcp.mcp_client instead of strands.tools.mcp.mcp_client
"""

import warnings

from ...mcp.mcp_client import MCPClient, ToolFilters

warnings.warn(
    "Importing from 'strands.tools.mcp.mcp_client' is deprecated. "
    "Use 'strands.mcp' or 'strands.mcp.mcp_client' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["MCPClient", "ToolFilters"]
