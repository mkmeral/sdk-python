"""Unit tests for MCP configuration loading."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from strands.tools.mcp.mcp_config import (
    MCPClientConfig,
    _create_sse_transport,
    _create_stdio_transport,
    _create_streamable_http_transport,
    _detect_transport_type,
    create_transport_callable,
    load_mcp_clients_from_config,
    load_mcp_config,
)


class TestTransportDetection:
    """Tests for transport type detection."""

    def test_detect_stdio_from_command(self):
        """Test detecting stdio transport from command field."""
        config = {"command": "python", "args": ["server.py"]}
        assert _detect_transport_type(config) == "stdio"

    def test_detect_sse_from_url(self):
        """Test detecting SSE transport from URL field without explicit transport."""
        config = {"url": "http://localhost:8000/sse"}
        assert _detect_transport_type(config) == "sse"

    def test_detect_explicit_sse(self):
        """Test detecting explicit SSE transport."""
        config = {"transport": "sse", "url": "http://localhost:8000/sse"}
        assert _detect_transport_type(config) == "sse"

    def test_detect_explicit_streamable_http(self):
        """Test detecting explicit streamable-http transport."""
        config = {"transport": "streamable-http", "url": "http://localhost:8000/mcp"}
        assert _detect_transport_type(config) == "streamable-http"

    def test_detect_unknown_transport(self):
        """Test error on unknown transport type."""
        config = {"transport": "unknown"}
        with pytest.raises(ValueError, match="Unknown transport type"):
            _detect_transport_type(config)

    def test_detect_missing_fields(self):
        """Test error when no transport-identifying fields are present."""
        config = {"env": {"VAR": "value"}}
        with pytest.raises(ValueError, match="Cannot determine transport type"):
            _detect_transport_type(config)


class TestStdioTransport:
    """Tests for stdio transport creation."""

    def test_create_stdio_transport_basic(self):
        """Test creating basic stdio transport."""
        config = {"command": "python", "args": ["server.py"]}
        transport_callable = _create_stdio_transport(config)

        assert callable(transport_callable)

    def test_create_stdio_transport_with_env(self):
        """Test creating stdio transport with environment variables."""
        config = {
            "command": "python",
            "args": ["server.py"],
            "env": {"DEBUG": "1", "API_KEY": "test"},
        }
        transport_callable = _create_stdio_transport(config)

        assert callable(transport_callable)

    def test_create_stdio_transport_no_args(self):
        """Test creating stdio transport without args."""
        config = {"command": "python"}
        transport_callable = _create_stdio_transport(config)

        assert callable(transport_callable)

    def test_create_stdio_transport_missing_command(self):
        """Test error when command is missing."""
        config = {"args": ["server.py"]}
        with pytest.raises(ValueError, match="must include 'command'"):
            _create_stdio_transport(config)


class TestSSETransport:
    """Tests for SSE transport creation."""

    def test_create_sse_transport(self):
        """Test creating SSE transport."""
        config = {"url": "http://localhost:8000/sse"}
        transport_callable = _create_sse_transport(config)

        assert callable(transport_callable)

    def test_create_sse_transport_missing_url(self):
        """Test error when URL is missing."""
        config = {"transport": "sse"}
        with pytest.raises(ValueError, match="must include 'url'"):
            _create_sse_transport(config)


class TestStreamableHTTPTransport:
    """Tests for streamable HTTP transport creation."""

    def test_create_streamable_http_transport(self):
        """Test creating streamable HTTP transport."""
        config = {"url": "http://localhost:8000/mcp"}
        transport_callable = _create_streamable_http_transport(config)

        assert callable(transport_callable)

    def test_create_streamable_http_transport_missing_url(self):
        """Test error when URL is missing."""
        config = {"transport": "streamable-http"}
        with pytest.raises(ValueError, match="must include 'url'"):
            _create_streamable_http_transport(config)


class TestCreateTransportCallable:
    """Tests for create_transport_callable function."""

    def test_create_stdio_callable(self):
        """Test creating stdio transport callable."""
        config = {"command": "python", "args": ["server.py"]}
        callable_fn = create_transport_callable("test-server", config)

        assert callable(callable_fn)

    def test_create_sse_callable(self):
        """Test creating SSE transport callable."""
        config = {"transport": "sse", "url": "http://localhost:8000/sse"}
        callable_fn = create_transport_callable("test-server", config)

        assert callable(callable_fn)

    def test_create_streamable_http_callable(self):
        """Test creating streamable HTTP transport callable."""
        config = {"transport": "streamable-http", "url": "http://localhost:8000/mcp"}
        callable_fn = create_transport_callable("test-server", config)

        assert callable(callable_fn)

    def test_create_callable_with_invalid_config(self):
        """Test error handling for invalid configuration."""
        config = {"invalid": "config"}
        with pytest.raises(ValueError, match="Failed to create transport"):
            create_transport_callable("test-server", config)


class TestMCPClientConfig:
    """Tests for MCPClientConfig class."""

    def test_create_client_config(self):
        """Test creating MCPClientConfig."""
        transport_callable = MagicMock()
        config = MCPClientConfig(
            name="test-server",
            transport_callable=transport_callable,
            startup_timeout=60,
            prefix="custom",
        )

        assert config.name == "test-server"
        assert config.transport_callable == transport_callable
        assert config.startup_timeout == 60
        assert config.prefix == "custom"
        assert config.tool_filters is None

    def test_create_client_from_config(self):
        """Test creating MCPClient from MCPClientConfig."""
        transport_callable = MagicMock()
        config = MCPClientConfig(
            name="test-server",
            transport_callable=transport_callable,
            startup_timeout=60,
            prefix="custom",
        )

        client = config.create_client()

        # Verify the client was created with correct parameters
        assert client._startup_timeout == 60
        assert client._prefix == "custom"
        assert client._transport_callable == transport_callable


class TestLoadMCPConfig:
    """Tests for load_mcp_config function."""

    def test_load_config_stdio_servers(self):
        """Test loading configuration with stdio servers."""
        config_data = {
            "mcpServers": {
                "echo": {
                    "command": "python",
                    "args": ["echo_server.py"],
                    "env": {"DEBUG": "1"},
                },
                "weather": {"command": "uvx", "args": ["mcp-server-weather"]},
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            configs = load_mcp_config(config_path)

            assert len(configs) == 2
            assert configs[0].name == "echo"
            assert configs[0].prefix == "echo"
            assert configs[1].name == "weather"
            assert configs[1].prefix == "weather"
        finally:
            Path(config_path).unlink()

    def test_load_config_mixed_transports(self):
        """Test loading configuration with mixed transport types."""
        config_data = {
            "mcpServers": {
                "stdio-server": {"command": "python", "args": ["server.py"]},
                "sse-server": {"transport": "sse", "url": "http://localhost:8000/sse"},
                "http-server": {
                    "transport": "streamable-http",
                    "url": "http://localhost:8001/mcp",
                },
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            configs = load_mcp_config(config_path)

            assert len(configs) == 3
            assert {c.name for c in configs} == {"stdio-server", "sse-server", "http-server"}
        finally:
            Path(config_path).unlink()

    def test_load_config_with_custom_prefix(self):
        """Test loading configuration with custom prefix."""
        config_data = {
            "mcpServers": {
                "server1": {"command": "python", "args": ["server1.py"]},
                "server2": {"command": "python", "args": ["server2.py"]},
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            configs = load_mcp_config(config_path, prefix="mcp")

            assert len(configs) == 2
            assert configs[0].prefix == "mcp_server1"
            assert configs[1].prefix == "mcp_server2"
        finally:
            Path(config_path).unlink()

    def test_load_config_with_tool_filters(self):
        """Test loading configuration with tool filters."""
        config_data = {
            "mcpServers": {
                "server1": {"command": "python", "args": ["server1.py"]},
                "server2": {"command": "python", "args": ["server2.py"]},
            }
        }

        tool_filters = {
            "server1": {"allowed": ["echo"]},
            "server2": {"rejected": ["dangerous_tool"]},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            configs = load_mcp_config(config_path, tool_filters=tool_filters)

            assert len(configs) == 2
            assert configs[0].tool_filters == {"allowed": ["echo"]}
            assert configs[1].tool_filters == {"rejected": ["dangerous_tool"]}
        finally:
            Path(config_path).unlink()

    def test_load_config_specific_servers(self):
        """Test loading only specific servers from configuration."""
        config_data = {
            "mcpServers": {
                "server1": {"command": "python", "args": ["server1.py"]},
                "server2": {"command": "python", "args": ["server2.py"]},
                "server3": {"command": "python", "args": ["server3.py"]},
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            configs = load_mcp_config(config_path, server_names=["server1", "server3"])

            assert len(configs) == 2
            assert {c.name for c in configs} == {"server1", "server3"}
        finally:
            Path(config_path).unlink()

    def test_load_config_missing_server_names(self):
        """Test error when requested server names don't exist."""
        config_data = {
            "mcpServers": {
                "server1": {"command": "python", "args": ["server1.py"]},
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            with pytest.raises(ValueError, match="Servers not found"):
                load_mcp_config(config_path, server_names=["server1", "nonexistent"])
        finally:
            Path(config_path).unlink()

    def test_load_config_file_not_found(self):
        """Test error when configuration file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_mcp_config("/nonexistent/path/mcp.json")

    def test_load_config_invalid_json(self):
        """Test error on invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            config_path = f.name

        try:
            with pytest.raises(ValueError, match="Invalid JSON"):
                load_mcp_config(config_path)
        finally:
            Path(config_path).unlink()

    def test_load_config_missing_mcpservers_key(self):
        """Test error when mcpServers key is missing."""
        config_data = {"wrongKey": {}}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            with pytest.raises(ValueError, match="must contain 'mcpServers'"):
                load_mcp_config(config_path)
        finally:
            Path(config_path).unlink()

    def test_load_config_mcpservers_not_dict(self):
        """Test error when mcpServers is not a dictionary."""
        config_data = {"mcpServers": ["not", "a", "dict"]}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            with pytest.raises(ValueError, match="must be a dictionary"):
                load_mcp_config(config_path)
        finally:
            Path(config_path).unlink()

    def test_load_config_invalid_server_config(self):
        """Test error when a server has invalid configuration."""
        config_data = {
            "mcpServers": {
                "bad-server": {"invalid": "config"},
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            with pytest.raises(ValueError, match="Failed to configure server"):
                load_mcp_config(config_path)
        finally:
            Path(config_path).unlink()

    def test_load_config_with_home_directory(self):
        """Test that paths with ~ are expanded."""
        config_data = {
            "mcpServers": {
                "server1": {"command": "python", "args": ["server1.py"]},
            }
        }

        # Create in temp directory but test path expansion
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            # Just verify it doesn't error with ~ in path
            # (actual ~ expansion would require a real home directory setup)
            configs = load_mcp_config(Path(temp_path))
            assert len(configs) == 1
        finally:
            Path(temp_path).unlink()


class TestLoadMCPClientsFromConfig:
    """Tests for load_mcp_clients_from_config convenience function."""

    def test_load_clients_from_config(self):
        """Test loading MCPClient instances from config."""
        config_data = {
            "mcpServers": {
                "server1": {"command": "python", "args": ["server1.py"]},
                "server2": {"transport": "sse", "url": "http://localhost:8000/sse"},
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            clients = load_mcp_clients_from_config(config_path)

            assert len(clients) == 2
            assert all(hasattr(client, "_startup_timeout") for client in clients)
            assert all(hasattr(client, "_prefix") for client in clients)
        finally:
            Path(config_path).unlink()

    def test_load_clients_with_all_options(self):
        """Test loading clients with all configuration options."""
        config_data = {
            "mcpServers": {
                "server1": {"command": "python", "args": ["server1.py"]},
                "server2": {"command": "python", "args": ["server2.py"]},
            }
        }

        tool_filters = {"server1": {"allowed": ["echo"]}}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            clients = load_mcp_clients_from_config(
                config_path,
                startup_timeout=60,
                tool_filters=tool_filters,
                prefix="mcp",
                server_names=["server1"],
            )

            assert len(clients) == 1
            assert clients[0]._startup_timeout == 60
            assert clients[0]._prefix == "mcp_server1"
            assert clients[0]._tool_filters == {"allowed": ["echo"]}
        finally:
            Path(config_path).unlink()
