# Quick Start: MCP Configuration Loader

Get started with loading MCP servers from configuration files in under 5 minutes!

## 1. Create an mcp.json file

Create a file named `mcp.json` in your project directory:

```json
{
  "mcpServers": {
    "weather": {
      "command": "uvx",
      "args": ["mcp-server-weather"]
    }
  }
}
```

## 2. Load and use with Agent

```python
from strands import Agent
from strands.tools.mcp import load_mcp_clients_from_config

# Load MCP clients from config
clients = load_mcp_clients_from_config("mcp.json")

# Create agent
agent = Agent(tools=clients)

# Use the tools
result = agent("What's the weather in Tokyo?")
print(result)

# Cleanup
agent.cleanup()
```

That's it! The MCP server lifecycle is automatically managed by the Agent.

## Common Patterns

### Multiple Servers

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
    }
  }
}
```

### SSE or HTTP Servers

```json
{
  "mcpServers": {
    "web-api": {
      "transport": "sse",
      "url": "http://localhost:8000/sse"
    }
  }
}
```

### Filter Dangerous Tools

```python
clients = load_mcp_clients_from_config(
    "mcp.json",
    tool_filters={
        "database": {
            "rejected": ["drop_table", "delete_all", "truncate"]
        }
    }
)
```

### Load Specific Servers

```python
# Only load production servers
clients = load_mcp_clients_from_config(
    "mcp.json",
    server_names=["weather", "database"]
)
```

## Next Steps

- See [mcp-config-loader.md](../docs/mcp-config-loader.md) for full documentation
- Run [mcp_config_example.py](mcp_config_example.py) for working examples
- Check [mcp.json.example](mcp.json.example) for a complete config template

## Configuration Compatibility

Your `mcp.json` file is compatible with:
- ✅ Strands Agents SDK (this implementation)
- ✅ Claude Desktop
- ✅ Kiro
- ✅ Other MCP-compatible applications

You can use the same configuration file across all these tools!
