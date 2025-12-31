"""Integration tests for MCP configuration loading with real servers."""

import json
import tempfile
import threading
import time
from pathlib import Path

from strands import Agent
from strands.tools.mcp import load_mcp_clients_from_config, load_mcp_config


def start_sse_server(port: int):
    """Start a simple MCP server using SSE transport."""
    from mcp.server import FastMCP

    mcp = FastMCP("Config Test Server", port=port)

    @mcp.tool(description="Echo back the input")
    def echo(message: str) -> str:
        return f"Echo: {message}"

    @mcp.tool(description="Add two numbers")
    def add(x: int, y: int) -> int:
        return x + y

    mcp.run(transport="sse")


def test_load_stdio_server_from_config():
    """Test loading and using a stdio MCP server from config."""
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
        # Load clients from config
        clients = load_mcp_clients_from_config(config_path)

        assert len(clients) == 1

        # Use the client with an agent
        agent = Agent(tools=clients)

        # Verify the tool is available with the correct prefix
        assert "echo_echo" in agent.tool_names

        # Test tool execution
        result = agent.tool.echo_echo(to_echo="Hello from config!")
        assert "Hello from config!" in str(result)

        agent.cleanup()
    finally:
        Path(config_path).unlink()


def test_load_multiple_servers_from_config():
    """Test loading multiple MCP servers from a single config file."""
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
        # Load clients from config
        clients = load_mcp_clients_from_config(config_path)

        assert len(clients) == 2

        # Use both clients with an agent
        agent = Agent(tools=clients)

        # Verify tools from both servers are available
        assert "server1_echo" in agent.tool_names
        assert "server2_echo" in agent.tool_names

        # Test tools from both servers
        result1 = agent.tool.server1_echo(to_echo="Server 1")
        assert "Server 1" in str(result1)

        result2 = agent.tool.server2_echo(to_echo="Server 2")
        assert "Server 2" in str(result2)

        agent.cleanup()
    finally:
        Path(config_path).unlink()


def test_load_config_with_filters():
    """Test loading config with tool filters applied."""
    config_data = {
        "mcpServers": {
            "echo": {
                "command": "python",
                "args": ["tests_integ/mcp/echo_server.py"],
            }
        }
    }

    tool_filters = {"echo": {"allowed": ["echo"]}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        config_path = f.name

    try:
        clients = load_mcp_clients_from_config(config_path, tool_filters=tool_filters)

        agent = Agent(tools=clients)

        # Only 'echo' tool should be available, not other tools from echo_server
        assert "echo_echo" in agent.tool_names
        assert "echo_echo_with_delay" not in agent.tool_names

        agent.cleanup()
    finally:
        Path(config_path).unlink()


def test_load_sse_server_from_config():
    """Test loading and using an SSE MCP server from config."""
    # Start SSE server in background
    port = 8002
    server_thread = threading.Thread(target=start_sse_server, args=(port,), daemon=True)
    server_thread.start()
    time.sleep(2)  # Wait for server to start

    config_data = {
        "mcpServers": {
            "sse-test": {"transport": "sse", "url": f"http://127.0.0.1:{port}/sse"}
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        config_path = f.name

    try:
        clients = load_mcp_clients_from_config(config_path)

        assert len(clients) == 1

        agent = Agent(tools=clients)

        # Verify tools are available
        assert "sse-test_echo" in agent.tool_names
        assert "sse-test_add" in agent.tool_names

        # Test tool execution
        result = agent.tool["sse-test_add"](x=5, y=3)
        assert "8" in str(result)

        agent.cleanup()
    finally:
        Path(config_path).unlink()


def test_load_config_with_custom_prefix():
    """Test loading config with custom global prefix."""
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
        clients = load_mcp_clients_from_config(config_path, prefix="mcp")

        agent = Agent(tools=clients)

        # Tools should have the custom prefix
        assert "mcp_echo_echo" in agent.tool_names

        result = agent.tool.mcp_echo_echo(to_echo="Custom prefix test")
        assert "Custom prefix test" in str(result)

        agent.cleanup()
    finally:
        Path(config_path).unlink()


def test_load_specific_servers_from_config():
    """Test loading only specific servers from config."""
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
        clients = load_mcp_clients_from_config(config_path, server_names=["server1", "server3"])

        agent = Agent(tools=clients)

        # Only server1 and server3 tools should be available
        assert "server1_echo" in agent.tool_names
        assert "server3_echo" in agent.tool_names
        assert "server2_echo" not in agent.tool_names

        agent.cleanup()
    finally:
        Path(config_path).unlink()


def test_config_with_environment_variables():
    """Test loading config that uses environment variables."""
    import os

    # Set a test environment variable
    os.environ["TEST_MCP_VAR"] = "original_value"

    config_data = {
        "mcpServers": {
            "echo": {
                "command": "python",
                "args": ["tests_integ/mcp/echo_server.py"],
                "env": {"TEST_MCP_VAR": "overridden_value", "NEW_VAR": "new_value"},
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f)
        config_path = f.name

    try:
        clients = load_mcp_clients_from_config(config_path)

        # The client should be created successfully with merged environment
        agent = Agent(tools=clients)
        assert "echo_echo" in agent.tool_names

        agent.cleanup()
    finally:
        Path(config_path).unlink()
        # Clean up test environment variable
        del os.environ["TEST_MCP_VAR"]


def test_mcp_client_config_objects():
    """Test using MCPClientConfig objects for more control."""
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

        assert len(configs) == 1
        assert configs[0].name == "echo"
        assert configs[0].startup_timeout == 60

        # Create clients from configs
        clients = [config.create_client() for config in configs]

        agent = Agent(tools=clients)
        assert "echo_echo" in agent.tool_names

        agent.cleanup()
    finally:
        Path(config_path).unlink()


def test_agent_with_config_managed_clients():
    """Test that Agent properly manages MCP client lifecycle via ToolProvider."""
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
        clients = load_mcp_clients_from_config(config_path)

        # Client should not be started yet
        assert not clients[0]._tool_provider_started

        # Create agent - this should trigger client initialization via ToolProvider
        agent = Agent(tools=clients)

        # Now client should be started
        assert clients[0]._tool_provider_started

        # Use the tool
        result = agent("Echo the text 'lifecycle test' back to me")
        assert "lifecycle test" in str(result).lower()

        # Cleanup should stop the client
        agent.cleanup()

        # Client should be stopped after cleanup
        assert not clients[0]._tool_provider_started
    finally:
        Path(config_path).unlink()
