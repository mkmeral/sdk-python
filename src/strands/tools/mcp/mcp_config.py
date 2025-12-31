"""MCP configuration file loader.

This module provides functionality to load MCP clients from an mcp.json configuration file.
The configuration file format follows the standard used by Claude Desktop, Kiro, and other
MCP-compatible applications.

Example mcp.json format:
```json
{
  "mcpServers": {
    "server-name": {
      "command": "uvx",
      "args": ["package-name"],
      "env": {
        "ENV_VAR": "value"
      }
    },
    "sse-server": {
      "transport": "sse",
      "url": "http://localhost:8000/sse"
    },
    "http-server": {
      "transport": "streamable-http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Union

from mcp import StdioServerParameters, stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
from typing_extensions import TypedDict

from .mcp_client import MCPClient, ToolFilters
from .mcp_types import MCPTransport

logger = logging.getLogger(__name__)

# Type definitions for configuration


class StdioServerConfig(TypedDict, total=False):
    """Configuration for stdio-based MCP server."""

    command: str
    args: List[str]
    env: Dict[str, str]


class SSEServerConfig(TypedDict, total=False):
    """Configuration for SSE-based MCP server."""

    transport: Literal["sse"]
    url: str


class StreamableHTTPServerConfig(TypedDict, total=False):
    """Configuration for streamable HTTP-based MCP server."""

    transport: Literal["streamable-http"]
    url: str


# Union type for all server configurations
ServerConfig = Union[StdioServerConfig, SSEServerConfig, StreamableHTTPServerConfig]


class MCPServersConfig(TypedDict):
    """Root configuration structure for mcp.json."""

    mcpServers: Dict[str, ServerConfig]


class MCPClientConfig:
    """Configuration for creating an MCPClient instance from config.

    This class stores the configuration needed to create an MCPClient,
    including the transport callable and optional parameters.
    """

    def __init__(
        self,
        name: str,
        transport_callable: Callable[[], MCPTransport],
        *,
        startup_timeout: int = 30,
        tool_filters: Optional[ToolFilters] = None,
        prefix: Optional[str] = None,
    ):
        """Initialize MCPClientConfig.

        Args:
            name: Name of the MCP server
            transport_callable: Callable that returns an MCPTransport
            startup_timeout: Timeout for server initialization
            tool_filters: Optional filters for tools
            prefix: Optional prefix for tool names
        """
        self.name = name
        self.transport_callable = transport_callable
        self.startup_timeout = startup_timeout
        self.tool_filters = tool_filters
        self.prefix = prefix

    def create_client(self) -> MCPClient:
        """Create an MCPClient instance from this configuration.

        Returns:
            MCPClient: A new MCPClient instance
        """
        return MCPClient(
            self.transport_callable,
            startup_timeout=self.startup_timeout,
            tool_filters=self.tool_filters,
            prefix=self.prefix,
        )


def _create_stdio_transport(config: StdioServerConfig) -> Callable[[], MCPTransport]:
    """Create a stdio transport callable from configuration.

    Args:
        config: Stdio server configuration

    Returns:
        Callable that returns an MCPTransport for stdio

    Raises:
        ValueError: If required fields are missing
    """
    if "command" not in config:
        raise ValueError("stdio server configuration must include 'command' field")

    command = config["command"]
    args = config.get("args", [])
    env = config.get("env", {})

    # Merge environment variables with current environment
    merged_env = os.environ.copy()
    merged_env.update(env)

    def transport_callable() -> MCPTransport:
        params = StdioServerParameters(
            command=command,
            args=args,
            env=merged_env if env else None,
        )
        return stdio_client(params)

    return transport_callable


def _create_sse_transport(config: SSEServerConfig) -> Callable[[], MCPTransport]:
    """Create an SSE transport callable from configuration.

    Args:
        config: SSE server configuration

    Returns:
        Callable that returns an MCPTransport for SSE

    Raises:
        ValueError: If required fields are missing
    """
    if "url" not in config:
        raise ValueError("SSE server configuration must include 'url' field")

    url = config["url"]

    def transport_callable() -> MCPTransport:
        return sse_client(url)

    return transport_callable


def _create_streamable_http_transport(config: StreamableHTTPServerConfig) -> Callable[[], MCPTransport]:
    """Create a streamable HTTP transport callable from configuration.

    Args:
        config: Streamable HTTP server configuration

    Returns:
        Callable that returns an MCPTransport for streamable HTTP

    Raises:
        ValueError: If required fields are missing
    """
    if "url" not in config:
        raise ValueError("streamable-http server configuration must include 'url' field")

    url = config["url"]

    def transport_callable() -> MCPTransport:
        return streamablehttp_client(url=url)

    return transport_callable


def _detect_transport_type(config: ServerConfig) -> Literal["stdio", "sse", "streamable-http"]:
    """Detect the transport type from server configuration.

    Args:
        config: Server configuration

    Returns:
        Transport type: "stdio", "sse", or "streamable-http"

    Raises:
        ValueError: If transport type cannot be determined
    """
    # Explicit transport field takes precedence
    if "transport" in config:
        transport = config["transport"]  # type: ignore
        if transport in ("sse", "streamable-http"):
            return transport
        else:
            raise ValueError(f"Unknown transport type: {transport}")

    # Infer transport type from configuration fields
    if "command" in config:
        return "stdio"
    elif "url" in config:
        # Default to SSE if URL is provided without explicit transport
        return "sse"
    else:
        raise ValueError("Cannot determine transport type from configuration")


def create_transport_callable(server_name: str, config: ServerConfig) -> Callable[[], MCPTransport]:
    """Create a transport callable from server configuration.

    Args:
        server_name: Name of the server (for error messages)
        config: Server configuration

    Returns:
        Callable that returns an MCPTransport

    Raises:
        ValueError: If configuration is invalid
    """
    try:
        transport_type = _detect_transport_type(config)

        if transport_type == "stdio":
            return _create_stdio_transport(config)  # type: ignore
        elif transport_type == "sse":
            return _create_sse_transport(config)  # type: ignore
        elif transport_type == "streamable-http":
            return _create_streamable_http_transport(config)  # type: ignore
        else:
            raise ValueError(f"Unsupported transport type: {transport_type}")

    except Exception as e:
        raise ValueError(f"Failed to create transport for server '{server_name}': {e}") from e


def load_mcp_config(
    config_path: Union[str, Path],
    *,
    startup_timeout: int = 30,
    tool_filters: Optional[Dict[str, ToolFilters]] = None,
    prefix: Optional[str] = None,
    server_names: Optional[List[str]] = None,
) -> List[MCPClientConfig]:
    """Load MCP client configurations from an mcp.json file.

    This function parses an mcp.json configuration file and creates MCPClientConfig
    instances for each server defined in the file. The configurations can then be
    used to create MCPClient instances.

    Args:
        config_path: Path to the mcp.json configuration file
        startup_timeout: Default timeout for server initialization (default: 30)
        tool_filters: Optional dictionary mapping server names to ToolFilters
        prefix: Optional default prefix for all tool names (server name will be appended)
        server_names: Optional list of server names to load (loads all if None)

    Returns:
        List of MCPClientConfig instances

    Raises:
        FileNotFoundError: If configuration file doesn't exist
        ValueError: If configuration is invalid

    Example:
        ```python
        # Load all servers from config
        configs = load_mcp_config("mcp.json")
        clients = [config.create_client() for config in configs]

        # Load specific servers with custom prefixes
        configs = load_mcp_config(
            "mcp.json",
            server_names=["weather", "database"],
            tool_filters={"weather": {"allowed": ["get_weather"]}}
        )

        # Use with Agent
        from strands import Agent
        agent = Agent(tools=[config.create_client() for config in configs])
        ```
    """
    config_path = Path(config_path).expanduser()

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    logger.info("Loading MCP configuration from: %s", config_path)

    try:
        with open(config_path, "r") as f:
            config_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in configuration file: {e}") from e

    if "mcpServers" not in config_data:
        raise ValueError("Configuration file must contain 'mcpServers' key")

    mcp_servers: Dict[str, ServerConfig] = config_data["mcpServers"]

    if not isinstance(mcp_servers, dict):
        raise ValueError("'mcpServers' must be a dictionary")

    # Filter servers if specific names are requested
    if server_names is not None:
        missing_servers = set(server_names) - set(mcp_servers.keys())
        if missing_servers:
            raise ValueError(f"Servers not found in configuration: {missing_servers}")
        servers_to_load = {name: mcp_servers[name] for name in server_names}
    else:
        servers_to_load = mcp_servers

    client_configs: List[MCPClientConfig] = []

    for server_name, server_config in servers_to_load.items():
        logger.debug("Processing server configuration: %s", server_name)

        try:
            transport_callable = create_transport_callable(server_name, server_config)

            # Determine prefix for this server
            server_prefix = f"{prefix}_{server_name}" if prefix else server_name

            # Get filters for this server
            server_filters = tool_filters.get(server_name) if tool_filters else None

            client_config = MCPClientConfig(
                name=server_name,
                transport_callable=transport_callable,
                startup_timeout=startup_timeout,
                tool_filters=server_filters,
                prefix=server_prefix,
            )

            client_configs.append(client_config)
            logger.info("Configured MCP server: %s (prefix: %s)", server_name, server_prefix)

        except Exception as e:
            logger.error("Failed to configure server '%s': %s", server_name, e)
            raise ValueError(f"Failed to configure server '{server_name}': {e}") from e

    logger.info("Successfully loaded %d MCP server configuration(s)", len(client_configs))
    return client_configs


def load_mcp_clients_from_config(
    config_path: Union[str, Path],
    *,
    startup_timeout: int = 30,
    tool_filters: Optional[Dict[str, ToolFilters]] = None,
    prefix: Optional[str] = None,
    server_names: Optional[List[str]] = None,
) -> List[MCPClient]:
    """Load MCP clients from an mcp.json configuration file.

    This is a convenience function that loads the configuration and immediately
    creates MCPClient instances. For more control, use load_mcp_config() instead.

    Args:
        config_path: Path to the mcp.json configuration file
        startup_timeout: Default timeout for server initialization (default: 30)
        tool_filters: Optional dictionary mapping server names to ToolFilters
        prefix: Optional default prefix for all tool names (server name will be appended)
        server_names: Optional list of server names to load (loads all if None)

    Returns:
        List of MCPClient instances

    Raises:
        FileNotFoundError: If configuration file doesn't exist
        ValueError: If configuration is invalid

    Example:
        ```python
        from strands import Agent
        from strands.tools.mcp import load_mcp_clients_from_config

        # Load all servers and use with Agent
        clients = load_mcp_clients_from_config("mcp.json")
        agent = Agent(tools=clients)

        # The agent will automatically manage client lifecycles via ToolProvider
        result = agent("Use the weather tool to get weather for San Francisco")
        agent.cleanup()  # Automatically cleans up MCP clients
        ```
    """
    configs = load_mcp_config(
        config_path,
        startup_timeout=startup_timeout,
        tool_filters=tool_filters,
        prefix=prefix,
        server_names=server_names,
    )

    return [config.create_client() for config in configs]
