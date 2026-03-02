"""Tests for Agent as AgentTool functionality.

Tests that Agent implements the AgentTool interface and can be passed directly as a tool to another agent.
"""

import unittest.mock
from typing import Any

import pytest

from strands import Agent
from strands.types.tools import AgentTool, ToolSpec, ToolUse
from tests.fixtures.mocked_model_provider import MockedModelProvider


@pytest.fixture
def agent():
    """Create a basic agent with a mocked model."""
    model = MockedModelProvider(
        agent_responses=[
            {"role": "assistant", "content": [{"text": "researched result"}]},
        ]
    )
    return Agent(
        model=model,
        name="researcher",
        description="Researches topics thoroughly",
        callback_handler=None,
    )


def test_agent_is_agent_tool(agent):
    """Agent should be an instance of AgentTool."""
    assert isinstance(agent, AgentTool)


def test_tool_name(agent):
    """tool_name should be derived from agent name."""
    assert agent.tool_name == "researcher"


def test_tool_name_sanitization():
    """tool_name should sanitize invalid characters."""
    model = MockedModelProvider(agent_responses=[])
    agent = Agent(model=model, name="My Research Agent!", callback_handler=None)
    assert agent.tool_name == "My_Research_Agent_"


def test_tool_name_truncation():
    """tool_name should be truncated to 64 characters."""
    model = MockedModelProvider(agent_responses=[])
    long_name = "a" * 100
    agent = Agent(model=model, name=long_name, callback_handler=None)
    assert len(agent.tool_name) == 64


def test_tool_spec(agent):
    """tool_spec should return a valid ToolSpec with prompt parameter."""
    spec = agent.tool_spec
    assert spec["name"] == "researcher"
    assert spec["description"] == "Researches topics thoroughly"
    assert "json" in spec["inputSchema"]
    schema = spec["inputSchema"]["json"]
    assert "prompt" in schema["properties"]
    assert schema["required"] == ["prompt"]


def test_tool_spec_default_description():
    """tool_spec should use a default description when none is provided."""
    model = MockedModelProvider(agent_responses=[])
    agent = Agent(model=model, name="researcher", callback_handler=None)
    spec = agent.tool_spec
    assert spec["description"] == "Agent: researcher"


def test_tool_type(agent):
    """tool_type should return 'agent'."""
    assert agent.tool_type == "agent"


@pytest.mark.asyncio
async def test_stream(agent):
    """stream should invoke the agent and yield a ToolResultEvent."""
    tool_use: ToolUse = {
        "name": "researcher",
        "toolUseId": "test-id-123",
        "input": {"prompt": "research quantum computing"},
    }

    events = []
    async for event in agent.stream(tool_use, {}):
        events.append(event)

    assert len(events) == 1
    result = events[0]["tool_result"]
    assert result["toolUseId"] == "test-id-123"
    assert result["status"] == "success"
    assert len(result["content"]) == 1
    assert "researched result" in result["content"][0]["text"]


def test_agent_passed_as_tool():
    """Agent should be passable directly in the tools list of another agent."""
    inner_model = MockedModelProvider(
        agent_responses=[
            {"role": "assistant", "content": [{"text": "inner response"}]},
        ]
    )
    inner_agent = Agent(
        model=inner_model,
        name="inner_agent",
        description="An inner agent",
        callback_handler=None,
    )

    outer_model = MockedModelProvider(
        agent_responses=[
            {"role": "assistant", "content": [{"text": "done"}]},
        ]
    )
    outer_agent = Agent(
        model=outer_model,
        tools=[inner_agent],
        callback_handler=None,
    )

    assert "inner_agent" in outer_agent.tool_names
