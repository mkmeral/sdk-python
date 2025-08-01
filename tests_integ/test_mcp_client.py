import base64
import json
import os
import threading
import time
from typing import List, Literal

import pytest
from mcp import StdioServerParameters, stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import ImageContent as MCPImageContent

from strands import Agent
from strands.tools.mcp.mcp_client import MCPClient
from strands.tools.mcp.mcp_types import MCPTransport
from strands.types.content import Message
from strands.types.tools import ToolUse


def start_calculator_server(transport: Literal["sse", "streamable-http"], port=int):
    """
    Initialize and start an MCP calculator server for integration testing.

    This function creates a FastMCP server instance that provides a simple
    calculator tool for performing addition operations. The server uses
    Server-Sent Events (SSE) transport for communication, making it accessible
    over HTTP.
    """
    from mcp.server import FastMCP

    mcp = FastMCP("Calculator Server", port=port)

    @mcp.tool(description="Calculator tool which performs calculations")
    def calculator(x: int, y: int) -> int:
        return x + y

    @mcp.tool(description="Generates a custom image")
    def generate_custom_image() -> MCPImageContent:
        try:
            with open("tests_integ/yellow.png", "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read())
                return MCPImageContent(type="image", data=encoded_image, mimeType="image/png")
        except Exception as e:
            print("Error while generating custom image: {}".format(e))

    mcp.run(transport=transport)


def test_mcp_client():
    """
    Test should yield output similar to the following
    {'role': 'user', 'content': [{'text': 'add 1 and 2, then echo the result back to me'}]}
    {'role': 'assistant', 'content': [{'text': "I'll help you add 1 and 2 and then echo the result back to you.\n\nFirst, I'll calculate 1 + 2:"}, {'toolUse': {'toolUseId': 'tooluse_17ptaKUxQB20ySZxwgiI_w', 'name': 'calculator', 'input': {'x': 1, 'y': 2}}}]}
    {'role': 'user', 'content': [{'toolResult': {'status': 'success', 'toolUseId': 'tooluse_17ptaKUxQB20ySZxwgiI_w', 'content': [{'text': '3'}]}}]}
    {'role': 'assistant', 'content': [{'text': "\n\nNow I'll echo the result back to you:"}, {'toolUse': {'toolUseId': 'tooluse_GlOc5SN8TE6ti8jVZJMBOg', 'name': 'echo', 'input': {'to_echo': '3'}}}]}
    {'role': 'user', 'content': [{'toolResult': {'status': 'success', 'toolUseId': 'tooluse_GlOc5SN8TE6ti8jVZJMBOg', 'content': [{'text': '3'}]}}]}
    {'role': 'assistant', 'content': [{'text': '\n\nThe result of adding 1 and 2 is 3.'}]}
    """  # noqa: E501

    server_thread = threading.Thread(
        target=start_calculator_server, kwargs={"transport": "sse", "port": 8000}, daemon=True
    )
    server_thread.start()
    time.sleep(2)  # wait for server to startup completely

    sse_mcp_client = MCPClient(lambda: sse_client("http://127.0.0.1:8000/sse"))
    stdio_mcp_client = MCPClient(
        lambda: stdio_client(StdioServerParameters(command="python", args=["tests_integ/echo_server.py"]))
    )
    with sse_mcp_client, stdio_mcp_client:
        agent = Agent(tools=sse_mcp_client.list_tools_sync() + stdio_mcp_client.list_tools_sync())
        agent("add 1 and 2, then echo the result back to me")

        tool_use_content_blocks = _messages_to_content_blocks(agent.messages)
        assert any([block["name"] == "echo" for block in tool_use_content_blocks])
        assert any([block["name"] == "calculator" for block in tool_use_content_blocks])

        image_prompt = """
        Generate a custom image, then tell me if the image is red, blue, yellow, pink, orange, or green. 
        RESPOND ONLY WITH THE COLOR
        """
        assert any(
            [
                "yellow".casefold() in block["text"].casefold()
                for block in agent(image_prompt).message["content"]
                if "text" in block
            ]
        )

        tool_use_id = "test-structured-content-123"
        result = stdio_mcp_client.call_tool_sync(
            tool_use_id=tool_use_id,
            name="echo_with_structured_content",
            arguments={"to_echo": "STRUCTURED_DATA_TEST"},
        )

        # With the new MCPToolResult, structured content is in its own field
        assert "structuredContent" in result
        assert result["structuredContent"]["result"] == {"echoed": "STRUCTURED_DATA_TEST"}

        # Verify the result is an MCPToolResult (at runtime it's just a dict, but type-wise it should be MCPToolResult)
        assert result["status"] == "success"
        assert result["toolUseId"] == tool_use_id

        assert len(result["content"]) == 1
        assert json.loads(result["content"][0]["text"]) == {"echoed": "STRUCTURED_DATA_TEST"}


def test_can_reuse_mcp_client():
    stdio_mcp_client = MCPClient(
        lambda: stdio_client(StdioServerParameters(command="python", args=["tests_integ/echo_server.py"]))
    )
    with stdio_mcp_client:
        stdio_mcp_client.list_tools_sync()
        pass
    with stdio_mcp_client:
        agent = Agent(tools=stdio_mcp_client.list_tools_sync())
        agent("echo the following to me <to_echo>DOG</to_echo>")

        tool_use_content_blocks = _messages_to_content_blocks(agent.messages)
        assert any([block["name"] == "echo" for block in tool_use_content_blocks])


@pytest.mark.asyncio
async def test_mcp_client_async_structured_content():
    """Test that async MCP client calls properly handle structured content.

    This test demonstrates how tools configure structured output: FastMCP automatically
    constructs structured output schema from method signature when structured_output=True
    is set in the @mcp.tool decorator. The return type annotation defines the structure
    that appears in structuredContent field.
    """
    stdio_mcp_client = MCPClient(
        lambda: stdio_client(StdioServerParameters(command="python", args=["tests_integ/echo_server.py"]))
    )

    with stdio_mcp_client:
        tool_use_id = "test-async-structured-content-456"
        result = await stdio_mcp_client.call_tool_async(
            tool_use_id=tool_use_id,
            name="echo_with_structured_content",
            arguments={"to_echo": "ASYNC_STRUCTURED_TEST"},
        )

        # Verify structured content is in its own field
        assert "structuredContent" in result
        # "result" nesting is not part of the MCP Structured Content specification,
        # but rather a FastMCP implementation detail
        assert result["structuredContent"]["result"] == {"echoed": "ASYNC_STRUCTURED_TEST"}

        # Verify basic MCPToolResult structure
        assert result["status"] in ["success", "error"]
        assert result["toolUseId"] == tool_use_id

        assert len(result["content"]) == 1
        assert json.loads(result["content"][0]["text"]) == {"echoed": "ASYNC_STRUCTURED_TEST"}


def test_mcp_client_without_structured_content():
    """Test that MCP client works correctly when tools don't return structured content."""
    stdio_mcp_client = MCPClient(
        lambda: stdio_client(StdioServerParameters(command="python", args=["tests_integ/echo_server.py"]))
    )

    with stdio_mcp_client:
        tool_use_id = "test-no-structured-content-789"
        result = stdio_mcp_client.call_tool_sync(
            tool_use_id=tool_use_id,
            name="echo",  # This tool doesn't return structured content
            arguments={"to_echo": "SIMPLE_ECHO_TEST"},
        )

        # Verify no structured content when tool doesn't provide it
        assert result.get("structuredContent") is None

        # Verify basic result structure
        assert result["status"] == "success"
        assert result["toolUseId"] == tool_use_id
        assert result["content"] == [{"text": "SIMPLE_ECHO_TEST"}]


@pytest.mark.skipif(
    condition=os.environ.get("GITHUB_ACTIONS") == "true",
    reason="streamable transport is failing in GitHub actions, debugging if linux compatibility issue",
)
def test_streamable_http_mcp_client():
    server_thread = threading.Thread(
        target=start_calculator_server, kwargs={"transport": "streamable-http", "port": 8001}, daemon=True
    )
    server_thread.start()
    time.sleep(2)  # wait for server to startup completely

    def transport_callback() -> MCPTransport:
        return streamablehttp_client(url="http://127.0.0.1:8001/mcp")

    streamable_http_client = MCPClient(transport_callback)
    with streamable_http_client:
        agent = Agent(tools=streamable_http_client.list_tools_sync())
        agent("add 1 and 2 using a calculator")

        tool_use_content_blocks = _messages_to_content_blocks(agent.messages)
        assert any([block["name"] == "calculator" for block in tool_use_content_blocks])


def _messages_to_content_blocks(messages: List[Message]) -> List[ToolUse]:
    return [block["toolUse"] for message in messages for block in message["content"] if "toolUse" in block]
