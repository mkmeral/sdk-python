"""Model Context Protocol (MCP) integration.

This package provides integration with the Model Context Protocol (MCP), a standardized
protocol for connecting AI systems with external tools, resources, and data sources.

MCP enables:
- **Tools**: Expose callable functions that can be invoked by AI agents
- **Resources**: Provide access to data sources and content
- **Prompts**: Define reusable prompt templates
- **Elicitation**: Handle interactive flows with users or systems

Key components:
- MCPClient: Manages connections to MCP servers
- MCPAgentTool: Adapts MCP tools to the agent framework
- MCPTransport: Defines transport layer abstractions
- ToolFilters: Configure which tools to load from servers

Example usage:
    ```python
    from strands.mcp import MCPClient
    from mcp.client.stdio import stdio_client
    
    # Connect to an MCP server
    transport = stdio_client({"command": "mcp-server", "args": []})
    
    with MCPClient(transport) as client:
        # List available tools
        tools = client.list_tools_sync()
        
        # Call a tool
        result = client.call_tool_sync(
            tool_use_id="123",
            name="calculator",
            arguments={"expression": "2 + 2"}
        )
    ```

- Docs: https://www.anthropic.com/news/model-context-protocol

Note:
    This module was moved from strands.tools.mcp in version X.X.X to better
    reflect its expanded scope beyond just tools. The old import path is
    maintained for backwards compatibility but will issue a deprecation warning.
"""

from .mcp_agent_tool import MCPAgentTool
from .mcp_client import MCPClient, ToolFilters
from .mcp_types import MCPTransport

__all__ = ["MCPAgentTool", "MCPClient", "MCPTransport", "ToolFilters"]
