"""Backwards compatibility module for MCP.

DEPRECATED: MCP has been moved to strands.mcp.
This module provides backwards compatibility for code that imports from strands.tools.mcp.

Please update your imports to use:
    from strands.mcp import MCPClient, MCPAgentTool, MCPTransport, ToolFilters

instead of:
    from strands.tools.mcp import MCPClient, MCPAgentTool, MCPTransport, ToolFilters

- Docs: https://www.anthropic.com/news/model-context-protocol
"""

import warnings

# Import from the new location
from ...mcp import MCPAgentTool, MCPClient, MCPTransport, ToolFilters

# Issue deprecation warning when this module is imported
warnings.warn(
    "Importing from 'strands.tools.mcp' is deprecated. "
    "MCP has been moved to 'strands.mcp'. "
    "Please update your imports to use 'from strands.mcp import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["MCPAgentTool", "MCPClient", "MCPTransport", "ToolFilters"]
