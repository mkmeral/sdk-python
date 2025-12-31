"""Example: Loading MCP servers from mcp.json configuration.

This example demonstrates how to use the MCP configuration loader to
set up multiple MCP servers from a single configuration file.
"""

import json
import tempfile
from pathlib import Path

from strands import Agent
from strands.tools.mcp import load_mcp_clients_from_config, load_mcp_config


def example_basic_usage():
    """Basic example: Load all servers from config."""
    print("=" * 60)
    print("Example 1: Basic Usage")
    print("=" * 60)

    # Create a sample mcp.json configuration
    config_data = {
        "mcpServers": {
            "echo": {
                "command": "python",
                "args": ["tests_integ/mcp/echo_server.py"],
            }
        }
    }

    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        config_path = f.name

    try:
        # Load MCP clients from configuration
        clients = load_mcp_clients_from_config(config_path)
        print(f"✓ Loaded {len(clients)} MCP client(s)")

        # Create agent with MCP tools
        agent = Agent(tools=clients)
        print(f"✓ Agent has {len(agent.tool_names)} tool(s): {agent.tool_names}")

        # Use the tool
        result = agent.tool.echo_echo(to_echo="Hello from config!")
        print(f"✓ Tool result: {result['content'][0]['text']}")

        # Cleanup
        agent.cleanup()
        print("✓ Cleanup complete")

    finally:
        Path(config_path).unlink()

    print()


def example_multiple_servers():
    """Example: Load multiple MCP servers."""
    print("=" * 60)
    print("Example 2: Multiple Servers")
    print("=" * 60)

    # Create configuration with multiple servers
    config_data = {
        "mcpServers": {
            "server1": {
                "command": "python",
                "args": ["tests_integ/mcp/echo_server.py"],
            },
            "server2": {
                "command": "python",
                "args": ["tests_integ/mcp/echo_server.py"],
            },
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        config_path = f.name

    try:
        clients = load_mcp_clients_from_config(config_path)
        print(f"✓ Loaded {len(clients)} MCP clients")

        agent = Agent(tools=clients)
        print(f"✓ Agent has tools: {agent.tool_names}")

        # Use tools from different servers
        result1 = agent.tool.server1_echo(to_echo="From server 1")
        result2 = agent.tool.server2_echo(to_echo="From server 2")

        print(f"✓ Server 1 result: {result1['content'][0]['text']}")
        print(f"✓ Server 2 result: {result2['content'][0]['text']}")

        agent.cleanup()
        print("✓ Cleanup complete")

    finally:
        Path(config_path).unlink()

    print()


def example_with_filters():
    """Example: Load with tool filters."""
    print("=" * 60)
    print("Example 3: Tool Filtering")
    print("=" * 60)

    config_data = {
        "mcpServers": {
            "echo": {
                "command": "python",
                "args": ["tests_integ/mcp/echo_server.py"],
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        config_path = f.name

    try:
        # Load with filters - only allow 'echo' tool
        clients = load_mcp_clients_from_config(
            config_path, tool_filters={"echo": {"allowed": ["echo"]}}
        )

        agent = Agent(tools=clients)
        print(f"✓ Filtered tools: {agent.tool_names}")
        print(f"  (other tools from echo_server are filtered out)")

        agent.cleanup()
        print("✓ Cleanup complete")

    finally:
        Path(config_path).unlink()

    print()


def example_custom_prefix():
    """Example: Use custom prefix."""
    print("=" * 60)
    print("Example 4: Custom Prefix")
    print("=" * 60)

    config_data = {
        "mcpServers": {
            "echo": {
                "command": "python",
                "args": ["tests_integ/mcp/echo_server.py"],
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        config_path = f.name

    try:
        # Load with custom global prefix
        clients = load_mcp_clients_from_config(config_path, prefix="mcp")

        agent = Agent(tools=clients)
        print(f"✓ Tools with custom prefix: {agent.tool_names}")
        print(f"  (prefix 'mcp' + server name 'echo' + tool name)")

        agent.cleanup()
        print("✓ Cleanup complete")

    finally:
        Path(config_path).unlink()

    print()


def example_selective_loading():
    """Example: Load only specific servers."""
    print("=" * 60)
    print("Example 5: Selective Server Loading")
    print("=" * 60)

    config_data = {
        "mcpServers": {
            "server1": {
                "command": "python",
                "args": ["tests_integ/mcp/echo_server.py"],
            },
            "server2": {
                "command": "python",
                "args": ["tests_integ/mcp/echo_server.py"],
            },
            "server3": {
                "command": "python",
                "args": ["tests_integ/mcp/echo_server.py"],
            },
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        config_path = f.name

    try:
        # Load only server1 and server3
        clients = load_mcp_clients_from_config(
            config_path, server_names=["server1", "server3"]
        )

        print(f"✓ Loaded {len(clients)} of 3 available servers")

        agent = Agent(tools=clients)
        available_servers = {name.split("_")[0] for name in agent.tool_names}
        print(f"✓ Available servers: {available_servers}")
        print(f"  (server2 was not loaded)")

        agent.cleanup()
        print("✓ Cleanup complete")

    finally:
        Path(config_path).unlink()

    print()


def example_advanced_config():
    """Example: Using MCPClientConfig for advanced control."""
    print("=" * 60)
    print("Example 6: Advanced Configuration")
    print("=" * 60)

    config_data = {
        "mcpServers": {
            "echo": {
                "command": "python",
                "args": ["tests_integ/mcp/echo_server.py"],
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        config_path = f.name

    try:
        # Load config objects instead of clients
        configs = load_mcp_config(config_path, startup_timeout=60)

        print(f"✓ Loaded {len(configs)} configuration(s)")
        for config in configs:
            print(f"  - {config.name}: timeout={config.startup_timeout}s, prefix={config.prefix}")

        # Modify configuration before creating client
        configs[0].startup_timeout = 120
        print(f"✓ Modified timeout to {configs[0].startup_timeout}s")

        # Create clients from configs
        clients = [config.create_client() for config in configs]

        agent = Agent(tools=clients)
        print(f"✓ Created agent with custom configuration")

        agent.cleanup()
        print("✓ Cleanup complete")

    finally:
        Path(config_path).unlink()

    print()


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("MCP Configuration Loader Examples")
    print("=" * 60 + "\n")

    try:
        example_basic_usage()
        example_multiple_servers()
        example_with_filters()
        example_custom_prefix()
        example_selective_loading()
        example_advanced_config()

        print("=" * 60)
        print("All examples completed successfully! ✓")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
