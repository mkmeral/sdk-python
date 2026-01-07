"""Backwards compatibility for mcp_agent_tool module.

DEPRECATED: Import from strands.mcp.mcp_agent_tool instead of strands.tools.mcp.mcp_agent_tool
"""

import warnings

from ...mcp.mcp_agent_tool import MCPAgentTool

warnings.warn(
    "Importing from 'strands.tools.mcp.mcp_agent_tool' is deprecated. "
    "Use 'strands.mcp' or 'strands.mcp.mcp_agent_tool' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["MCPAgentTool"]
