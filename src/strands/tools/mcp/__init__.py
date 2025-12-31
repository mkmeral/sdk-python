"""Model Context Protocol (MCP) integration.

This package provides integration with the Model Context Protocol (MCP), allowing agents to use tools provided by MCP
servers.

- Docs: https://www.anthropic.com/news/model-context-protocol
"""

from .mcp_agent_tool import MCPAgentTool
from .mcp_client import MCPClient, ToolFilters
from .mcp_config import (
    MCPClientConfig,
    load_mcp_clients_from_config,
    load_mcp_config,
)
from .mcp_types import MCPTransport

__all__ = [
    "MCPAgentTool",
    "MCPClient",
    "MCPClientConfig",
    "MCPTransport",
    "ToolFilters",
    "load_mcp_clients_from_config",
    "load_mcp_config",
]
