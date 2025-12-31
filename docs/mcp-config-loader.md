# MCP Configuration Loader

This module provides functionality to load MCP (Model Context Protocol) clients from a standard `mcp.json` configuration file. This makes it easy to configure multiple MCP servers and use them with Strands agents.

## Features

- ✅ Supports stdio, SSE, and streamable-http transports
- ✅ Compatible with standard mcp.json format (Claude Desktop, Kiro, etc.)
- ✅ Automatic lifecycle management via ToolProvider pattern
- ✅ Support for tool filtering and prefixing
- ✅ Environment variable merging for stdio servers
- ✅ Selective server loading

## Usage

### Basic Usage

Create an `mcp.json` file:

```json
{
  "mcpServers": {
    "weather": {
      "command": "uvx",
      "args": ["mcp-server-weather"]
    },
    "database": {
      "command": "python",
      "args": ["-m", "mcp_server_postgres"],
      "env": {
        "DATABASE_URL": "postgresql://localhost/mydb"
      }
    },
    "web-search": {
      "transport": "sse",
      "url": "http://localhost:8000/sse"
    }
  }
}
```

Load and use with an agent:

```python
from strands import Agent
from strands.tools.mcp import load_mcp_clients_from_config

# Load all MCP clients from config
clients = load_mcp_clients_from_config("mcp.json")

# Create agent with MCP tools
agent = Agent(tools=clients)

# Use the tools - they're automatically prefixed with server name
result = agent("What's the weather in San Francisco?")

# Cleanup happens automatically
agent.cleanup()
```

### Advanced Usage

#### Load Specific Servers

```python
# Only load specific servers
clients = load_mcp_clients_from_config(
    "mcp.json",
    server_names=["weather", "database"]
)
```

#### Custom Prefixes

```python
# Add custom prefix to all tools
clients = load_mcp_clients_from_config(
    "mcp.json",
    prefix="mcp"  # Tools will be named: mcp_weather_get_weather, etc.
)
```

#### Tool Filtering

```python
# Filter tools per server
clients = load_mcp_clients_from_config(
    "mcp.json",
    tool_filters={
        "weather": {"allowed": ["get_weather", "get_forecast"]},
        "database": {"rejected": ["drop_table", "delete_all"]}
    }
)
```

#### Custom Timeouts

```python
# Configure startup timeout
clients = load_mcp_clients_from_config(
    "mcp.json",
    startup_timeout=60  # Wait up to 60 seconds for server initialization
)
```

### Using MCPClientConfig for More Control

For advanced use cases, you can work with `MCPClientConfig` objects directly:

```python
from strands.tools.mcp import load_mcp_config

# Load configurations without creating clients yet
configs = load_mcp_config("mcp.json")

# Inspect or modify configurations
for config in configs:
    print(f"Server: {config.name}")
    print(f"Prefix: {config.prefix}")
    if config.name == "database":
        config.startup_timeout = 120  # Give database more time

# Create clients when ready
clients = [config.create_client() for config in configs]

# Use with agent
agent = Agent(tools=clients)
```

## Configuration Format

The `mcp.json` format supports three transport types:

### Stdio Transport

For local command-line based MCP servers:

```json
{
  "mcpServers": {
    "server-name": {
      "command": "uvx",
      "args": ["mcp-server-package"],
      "env": {
        "API_KEY": "your-key",
        "DEBUG": "true"
      }
    }
  }
}
```

### SSE Transport

For Server-Sent Events based MCP servers:

```json
{
  "mcpServers": {
    "server-name": {
      "transport": "sse",
      "url": "http://localhost:8000/sse"
    }
  }
}
```

### Streamable HTTP Transport

For HTTP streaming based MCP servers:

```json
{
  "mcpServers": {
    "server-name": {
      "transport": "streamable-http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

## Tool Naming

By default, tools are prefixed with the server name to avoid conflicts:

- Server name: `weather`
- Original tool: `get_weather`
- Available as: `weather_get_weather`

You can customize this:

```python
# Add global prefix
clients = load_mcp_clients_from_config("mcp.json", prefix="mcp")
# Result: mcp_weather_get_weather

# Or use empty prefix for no prefixing (not recommended with multiple servers)
configs = load_mcp_config("mcp.json")
configs[0].prefix = ""  # Direct tool names (be careful of conflicts!)
```

## Lifecycle Management

MCP clients loaded via config automatically integrate with the Agent's ToolProvider system:

```python
clients = load_mcp_clients_from_config("mcp.json")

# Clients are NOT started yet
print(clients[0]._tool_provider_started)  # False

# Agent starts them on initialization
agent = Agent(tools=clients)

# Now they're running
print(clients[0]._tool_provider_started)  # True

# Cleanup stops all clients
agent.cleanup()

# Stopped after cleanup
print(clients[0]._tool_provider_started)  # False
```

## Examples

### Example 1: Multiple MCP Servers

```python
from strands import Agent
from strands.tools.mcp import load_mcp_clients_from_config

# Load multiple servers
clients = load_mcp_clients_from_config("mcp.json")

agent = Agent(tools=clients)

# Agent can use tools from any server
result = agent("""
    1. Get the weather for San Francisco
    2. Search the web for "best restaurants in San Francisco"
    3. Store the results in the database
""")

agent.cleanup()
```

### Example 2: Filtered Tools

```python
# Only allow safe database operations
clients = load_mcp_clients_from_config(
    "mcp.json",
    tool_filters={
        "database": {
            "allowed": ["select", "insert", "update"],
            "rejected": ["drop", "delete", "truncate"]
        }
    }
)

agent = Agent(tools=clients)
# Agent can only use safe database operations
```

### Example 3: Development vs Production

```python
import os

config_file = "mcp.dev.json" if os.getenv("ENV") == "dev" else "mcp.json"

clients = load_mcp_clients_from_config(
    config_file,
    startup_timeout=120,  # Longer timeout for production
)

agent = Agent(tools=clients)
```

## API Reference

### `load_mcp_clients_from_config()`

Convenience function that loads and immediately creates MCPClient instances.

```python
def load_mcp_clients_from_config(
    config_path: Union[str, Path],
    *,
    startup_timeout: int = 30,
    tool_filters: Optional[Dict[str, ToolFilters]] = None,
    prefix: Optional[str] = None,
    server_names: Optional[List[str]] = None,
) -> List[MCPClient]:
    ...
```

**Parameters:**
- `config_path`: Path to mcp.json file
- `startup_timeout`: Timeout in seconds for server initialization (default: 30)
- `tool_filters`: Dictionary mapping server names to ToolFilters
- `prefix`: Global prefix for all tool names (server name is appended)
- `server_names`: Optional list of server names to load (loads all if None)

**Returns:** List of MCPClient instances ready to use with Agent

### `load_mcp_config()`

Loads configuration and returns MCPClientConfig objects for more control.

```python
def load_mcp_config(
    config_path: Union[str, Path],
    *,
    startup_timeout: int = 30,
    tool_filters: Optional[Dict[str, ToolFilters]] = None,
    prefix: Optional[str] = None,
    server_names: Optional[List[str]] = None,
) -> List[MCPClientConfig]:
    ...
```

**Parameters:** Same as `load_mcp_clients_from_config()`

**Returns:** List of MCPClientConfig objects that can be modified before creating clients

### `MCPClientConfig`

Configuration object for creating an MCPClient.

```python
class MCPClientConfig:
    name: str
    transport_callable: Callable[[], MCPTransport]
    startup_timeout: int
    tool_filters: Optional[ToolFilters]
    prefix: Optional[str]
    
    def create_client(self) -> MCPClient:
        """Create an MCPClient from this configuration."""
        ...
```

## Error Handling

The loader provides clear error messages for common issues:

```python
# File not found
try:
    clients = load_mcp_clients_from_config("missing.json")
except FileNotFoundError as e:
    print(f"Config file not found: {e}")

# Invalid JSON
try:
    clients = load_mcp_clients_from_config("invalid.json")
except ValueError as e:
    print(f"Invalid JSON: {e}")

# Missing server
try:
    clients = load_mcp_clients_from_config(
        "mcp.json",
        server_names=["nonexistent"]
    )
except ValueError as e:
    print(f"Server not found: {e}")

# Invalid configuration
try:
    clients = load_mcp_clients_from_config("bad-config.json")
except ValueError as e:
    print(f"Invalid config: {e}")
```

## Compatibility

This loader is compatible with mcp.json files used by:
- Claude Desktop
- Kiro
- Other MCP-compatible applications

You can use the same configuration file across different tools!

## See Also

- [MCP Documentation](https://www.anthropic.com/news/model-context-protocol)
- [MCP Client Documentation](https://strandsagents.com/latest/user-guide/concepts/tools/mcp-tools/)
- [Agent Documentation](https://strandsagents.com/latest/user-guide/concepts/agents/)
