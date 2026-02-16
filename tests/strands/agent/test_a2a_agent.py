"""Tests for A2AAgent class."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from a2a.client import ClientConfig
from a2a.types import AgentCard, Message, Part, Role, TextPart

from strands.agent.a2a_agent import A2AAgent
from strands.agent.agent_result import AgentResult


@pytest.fixture
def mock_agent_card():
    """Mock AgentCard for testing."""
    return AgentCard(
        name="test-agent",
        description="Test agent",
        url="http://localhost:8000",
        version="1.0.0",
        capabilities={},
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[],
    )


@pytest.fixture
def a2a_agent():
    """Create A2AAgent instance for testing."""
    return A2AAgent(endpoint="http://localhost:8000")


@pytest.fixture
def mock_a2a_client():
    """Create a mock A2A Client."""
    client = AsyncMock()
    client.get_card = AsyncMock()
    client.send_message = AsyncMock()
    return client


def test_init_with_defaults():
    """Test initialization with default parameters."""
    agent = A2AAgent(endpoint="http://localhost:8000")
    assert agent.endpoint == "http://localhost:8000"
    assert agent.timeout == 300
    assert agent._agent_card is None
    assert agent._a2a_client is None
    assert agent.name is None
    assert agent.description is None


def test_init_with_name_and_description():
    """Test initialization with custom name and description."""
    agent = A2AAgent(endpoint="http://localhost:8000", name="my-agent", description="My custom agent")
    assert agent.name == "my-agent"
    assert agent.description == "My custom agent"


def test_init_with_custom_timeout():
    """Test initialization with custom timeout."""
    agent = A2AAgent(endpoint="http://localhost:8000", timeout=600)
    assert agent.timeout == 600


def test_init_with_external_a2a_client_factory():
    """Test initialization with external A2A client factory."""
    external_factory = MagicMock()
    agent = A2AAgent(endpoint="http://localhost:8000", a2a_client_factory=external_factory)
    assert agent._a2a_client_factory is external_factory
    assert agent._a2a_client is None


@pytest.mark.asyncio
async def test_get_agent_card_no_factory(a2a_agent, mock_agent_card, mock_a2a_client):
    """Test agent card discovery without factory uses transient ClientFactory.connect()."""
    mock_a2a_client.get_card = AsyncMock(return_value=mock_agent_card)

    with patch("strands.agent.a2a_agent.ClientFactory") as mock_factory_class:
        mock_factory_class.connect = AsyncMock(return_value=mock_a2a_client)

        card = await a2a_agent.get_agent_card()

        mock_factory_class.connect.assert_called_once_with("http://localhost:8000")
        assert card == mock_agent_card
        assert a2a_agent._agent_card == mock_agent_card


@pytest.mark.asyncio
async def test_get_agent_card_with_factory(mock_agent_card, mock_a2a_client):
    """Test agent card discovery with factory uses factory's client config."""
    mock_config = MagicMock(spec=ClientConfig)
    mock_factory = MagicMock()
    mock_factory._config = mock_config

    mock_a2a_client.get_card = AsyncMock(return_value=mock_agent_card)

    agent = A2AAgent(endpoint="http://localhost:8000", a2a_client_factory=mock_factory)

    with patch("strands.agent.a2a_agent.ClientFactory") as mock_factory_class:
        mock_factory_class.connect = AsyncMock(return_value=mock_a2a_client)

        card = await agent.get_agent_card()

        mock_factory_class.connect.assert_called_once_with("http://localhost:8000", client_config=mock_config)
        assert card == mock_agent_card
        # Client should be cached
        assert agent._a2a_client is mock_a2a_client


@pytest.mark.asyncio
async def test_get_agent_card_with_factory_config_fallback(mock_agent_card, mock_a2a_client):
    """Test that factory with inaccessible _config falls back to default ClientConfig."""
    mock_factory = MagicMock(spec=[])  # No _config attribute

    mock_a2a_client.get_card = AsyncMock(return_value=mock_agent_card)

    agent = A2AAgent(endpoint="http://localhost:8000", a2a_client_factory=mock_factory)

    with patch("strands.agent.a2a_agent.ClientFactory") as mock_factory_class:
        mock_factory_class.connect = AsyncMock(return_value=mock_a2a_client)

        card = await agent.get_agent_card()

        # Should fall back to default ClientConfig
        call_args = mock_factory_class.connect.call_args
        assert call_args[0][0] == "http://localhost:8000"
        assert isinstance(call_args[1]["client_config"], ClientConfig)
        assert card == mock_agent_card


@pytest.mark.asyncio
async def test_get_agent_card_cached(a2a_agent, mock_agent_card):
    """Test that agent card is cached after first discovery."""
    a2a_agent._agent_card = mock_agent_card

    card = await a2a_agent.get_agent_card()

    assert card == mock_agent_card


@pytest.mark.asyncio
async def test_get_agent_card_populates_name_and_description(mock_agent_card, mock_a2a_client):
    """Test that agent card populates name and description if not set."""
    agent = A2AAgent(endpoint="http://localhost:8000")
    mock_a2a_client.get_card = AsyncMock(return_value=mock_agent_card)

    with patch("strands.agent.a2a_agent.ClientFactory") as mock_factory_class:
        mock_factory_class.connect = AsyncMock(return_value=mock_a2a_client)

        await agent.get_agent_card()

        assert agent.name == mock_agent_card.name
        assert agent.description == mock_agent_card.description


@pytest.mark.asyncio
async def test_get_agent_card_preserves_custom_name_and_description(mock_agent_card, mock_a2a_client):
    """Test that custom name and description are not overridden by agent card."""
    agent = A2AAgent(endpoint="http://localhost:8000", name="custom-name", description="Custom description")
    mock_a2a_client.get_card = AsyncMock(return_value=mock_agent_card)

    with patch("strands.agent.a2a_agent.ClientFactory") as mock_factory_class:
        mock_factory_class.connect = AsyncMock(return_value=mock_a2a_client)

        await agent.get_agent_card()

        assert agent.name == "custom-name"
        assert agent.description == "Custom description"


@pytest.mark.asyncio
async def test_get_or_create_client_caches_with_factory(mock_a2a_client):
    """Test that _get_or_create_client caches the client when factory is provided."""
    mock_config = MagicMock(spec=ClientConfig)
    mock_factory = MagicMock()
    mock_factory._config = mock_config

    agent = A2AAgent(endpoint="http://localhost:8000", a2a_client_factory=mock_factory)

    with patch("strands.agent.a2a_agent.ClientFactory") as mock_factory_class:
        mock_factory_class.connect = AsyncMock(return_value=mock_a2a_client)

        client1 = await agent._get_or_create_client()
        client2 = await agent._get_or_create_client()

        # Should only connect once, then return cached client
        mock_factory_class.connect.assert_called_once()
        assert client1 is client2
        assert client1 is mock_a2a_client


@pytest.mark.asyncio
async def test_get_or_create_client_transient_without_factory(mock_a2a_client):
    """Test that _get_or_create_client creates transient clients when no factory."""
    agent = A2AAgent(endpoint="http://localhost:8000")

    mock_client_1 = AsyncMock()
    mock_client_2 = AsyncMock()

    with patch("strands.agent.a2a_agent.ClientFactory") as mock_factory_class:
        mock_factory_class.connect = AsyncMock(side_effect=[mock_client_1, mock_client_2])

        client1 = await agent._get_or_create_client()
        client2 = await agent._get_or_create_client()

        # Should connect each time (transient)
        assert mock_factory_class.connect.call_count == 2
        assert client1 is mock_client_1
        assert client2 is mock_client_2


@pytest.mark.asyncio
async def test_invoke_async_success(a2a_agent, mock_agent_card, mock_a2a_client):
    """Test successful async invocation."""
    mock_response = Message(
        message_id=uuid4().hex,
        role=Role.agent,
        parts=[Part(TextPart(kind="text", text="Response"))],
    )

    async def mock_send_message(*args, **kwargs):
        yield mock_response

    mock_a2a_client.get_card = AsyncMock(return_value=mock_agent_card)
    mock_a2a_client.send_message = mock_send_message

    with patch("strands.agent.a2a_agent.ClientFactory") as mock_factory_class:
        mock_factory_class.connect = AsyncMock(return_value=mock_a2a_client)

        result = await a2a_agent.invoke_async("Hello")

        assert isinstance(result, AgentResult)
        assert result.message["content"][0]["text"] == "Response"


@pytest.mark.asyncio
async def test_invoke_async_no_prompt(a2a_agent):
    """Test that invoke_async raises ValueError when prompt is None."""
    with pytest.raises(ValueError, match="prompt is required"):
        await a2a_agent.invoke_async(None)


@pytest.mark.asyncio
async def test_invoke_async_no_response(a2a_agent, mock_agent_card, mock_a2a_client):
    """Test that invoke_async raises RuntimeError when no response received."""

    async def mock_send_message(*args, **kwargs):
        return
        yield  # Make it an async generator

    mock_a2a_client.get_card = AsyncMock(return_value=mock_agent_card)
    mock_a2a_client.send_message = mock_send_message

    with patch("strands.agent.a2a_agent.ClientFactory") as mock_factory_class:
        mock_factory_class.connect = AsyncMock(return_value=mock_a2a_client)

        with pytest.raises(RuntimeError, match="No response received"):
            await a2a_agent.invoke_async("Hello")


def test_call_sync(a2a_agent):
    """Test synchronous call method."""
    mock_result = AgentResult(
        stop_reason="end_turn",
        message={"role": "assistant", "content": [{"text": "Response"}]},
        metrics=MagicMock(),
        state={},
    )

    with patch("strands.agent.a2a_agent.run_async") as mock_run_async:
        mock_run_async.return_value = mock_result

        result = a2a_agent("Hello")

        assert result == mock_result
        mock_run_async.assert_called_once()


@pytest.mark.asyncio
async def test_stream_async_success(a2a_agent, mock_agent_card, mock_a2a_client):
    """Test successful async streaming."""
    mock_response = Message(
        message_id=uuid4().hex,
        role=Role.agent,
        parts=[Part(TextPart(kind="text", text="Response"))],
    )

    async def mock_send_message(*args, **kwargs):
        yield mock_response

    mock_a2a_client.get_card = AsyncMock(return_value=mock_agent_card)
    mock_a2a_client.send_message = mock_send_message

    with patch("strands.agent.a2a_agent.ClientFactory") as mock_factory_class:
        mock_factory_class.connect = AsyncMock(return_value=mock_a2a_client)

        events = []
        async for event in a2a_agent.stream_async("Hello"):
            events.append(event)

        assert len(events) == 2
        # First event is A2A stream event
        assert events[0]["type"] == "a2a_stream"
        assert events[0]["event"] == mock_response
        # Final event is AgentResult
        assert "result" in events[1]
        assert isinstance(events[1]["result"], AgentResult)
        assert events[1]["result"].message["content"][0]["text"] == "Response"


@pytest.mark.asyncio
async def test_stream_async_no_prompt(a2a_agent):
    """Test that stream_async raises ValueError when prompt is None."""
    with pytest.raises(ValueError, match="prompt is required"):
        async for _ in a2a_agent.stream_async(None):
            pass


@pytest.mark.asyncio
async def test_send_message_uses_cached_client_with_factory(mock_agent_card, mock_a2a_client):
    """Test _send_message reuses cached client when factory is provided."""
    mock_config = MagicMock(spec=ClientConfig)
    mock_factory = MagicMock()
    mock_factory._config = mock_config

    async def mock_send_message(*args, **kwargs):
        yield MagicMock()

    mock_a2a_client.get_card = AsyncMock(return_value=mock_agent_card)
    mock_a2a_client.send_message = mock_send_message

    agent = A2AAgent(endpoint="http://localhost:8000", a2a_client_factory=mock_factory)

    with patch("strands.agent.a2a_agent.ClientFactory") as mock_factory_class:
        mock_factory_class.connect = AsyncMock(return_value=mock_a2a_client)

        # First call: get card (creates + caches client)
        await agent.get_agent_card()
        # Second call: send message (reuses cached client)
        async for _ in agent._send_message("Hello"):
            pass

        # connect() should only be called once (cached)
        mock_factory_class.connect.assert_called_once()


@pytest.mark.asyncio
async def test_send_message_creates_transient_client(a2a_agent, mock_agent_card, mock_a2a_client):
    """Test _send_message creates transient clients when no factory provided."""
    mock_response = Message(
        message_id=uuid4().hex,
        role=Role.agent,
        parts=[Part(TextPart(kind="text", text="Response"))],
    )

    async def mock_send_message(*args, **kwargs):
        yield mock_response

    mock_a2a_client.get_card = AsyncMock(return_value=mock_agent_card)
    mock_a2a_client.send_message = mock_send_message

    with patch("strands.agent.a2a_agent.ClientFactory") as mock_factory_class:
        mock_factory_class.connect = AsyncMock(return_value=mock_a2a_client)

        # Two separate calls: get_agent_card + _send_message each create transient clients
        await a2a_agent.get_agent_card()
        async for _ in a2a_agent._send_message("Hello"):
            pass

        # Without factory, each _get_or_create_client() call creates a new transient client
        assert mock_factory_class.connect.call_count == 2


def test_is_complete_event_message(a2a_agent):
    """Test _is_complete_event returns True for Message."""
    mock_message = MagicMock(spec=Message)

    assert a2a_agent._is_complete_event(mock_message) is True


def test_is_complete_event_tuple_with_none_update(a2a_agent):
    """Test _is_complete_event returns True for tuple with None update event."""
    mock_task = MagicMock()

    assert a2a_agent._is_complete_event((mock_task, None)) is True


def test_is_complete_event_artifact_last_chunk(a2a_agent):
    """Test _is_complete_event handles TaskArtifactUpdateEvent last_chunk flag."""
    from a2a.types import TaskArtifactUpdateEvent

    mock_task = MagicMock()

    # last_chunk=True -> complete
    event_complete = MagicMock(spec=TaskArtifactUpdateEvent)
    event_complete.last_chunk = True
    assert a2a_agent._is_complete_event((mock_task, event_complete)) is True

    # last_chunk=False -> not complete
    event_incomplete = MagicMock(spec=TaskArtifactUpdateEvent)
    event_incomplete.last_chunk = False
    assert a2a_agent._is_complete_event((mock_task, event_incomplete)) is False

    # last_chunk=None -> not complete
    event_none = MagicMock(spec=TaskArtifactUpdateEvent)
    event_none.last_chunk = None
    assert a2a_agent._is_complete_event((mock_task, event_none)) is False


def test_is_complete_event_status_update(a2a_agent):
    """Test _is_complete_event handles TaskStatusUpdateEvent state."""
    from a2a.types import TaskState, TaskStatusUpdateEvent

    mock_task = MagicMock()

    # completed state -> complete
    event_completed = MagicMock(spec=TaskStatusUpdateEvent)
    event_completed.status = MagicMock()
    event_completed.status.state = TaskState.completed
    assert a2a_agent._is_complete_event((mock_task, event_completed)) is True

    # working state -> not complete
    event_working = MagicMock(spec=TaskStatusUpdateEvent)
    event_working.status = MagicMock()
    event_working.status.state = TaskState.working
    assert a2a_agent._is_complete_event((mock_task, event_working)) is False

    # no status -> not complete
    event_no_status = MagicMock(spec=TaskStatusUpdateEvent)
    event_no_status.status = None
    assert a2a_agent._is_complete_event((mock_task, event_no_status)) is False


def test_is_complete_event_unknown_type(a2a_agent):
    """Test _is_complete_event returns False for unknown event types."""
    assert a2a_agent._is_complete_event("unknown") is False


@pytest.mark.asyncio
async def test_stream_async_tracks_complete_events(a2a_agent, mock_agent_card, mock_a2a_client):
    """Test stream_async uses last complete event for final result."""
    from a2a.types import TaskState, TaskStatusUpdateEvent

    mock_task = MagicMock()
    mock_task.artifacts = None

    # First event: incomplete
    incomplete_event = MagicMock(spec=TaskStatusUpdateEvent)
    incomplete_event.status = MagicMock()
    incomplete_event.status.state = TaskState.working
    incomplete_event.status.message = None

    # Second event: complete
    complete_event = MagicMock(spec=TaskStatusUpdateEvent)
    complete_event.status = MagicMock()
    complete_event.status.state = TaskState.completed
    complete_event.status.message = MagicMock()
    complete_event.status.message.parts = []

    async def mock_send_message(*args, **kwargs):
        yield (mock_task, incomplete_event)
        yield (mock_task, complete_event)

    mock_a2a_client.get_card = AsyncMock(return_value=mock_agent_card)
    mock_a2a_client.send_message = mock_send_message

    with patch("strands.agent.a2a_agent.ClientFactory") as mock_factory_class:
        mock_factory_class.connect = AsyncMock(return_value=mock_a2a_client)

        events = []
        async for event in a2a_agent.stream_async("Hello"):
            events.append(event)

        # Should have 2 stream events + 1 result event
        assert len(events) == 3
        assert "result" in events[2]


@pytest.mark.asyncio
async def test_stream_async_falls_back_to_last_event(a2a_agent, mock_agent_card, mock_a2a_client):
    """Test stream_async falls back to last event when no complete event."""
    from a2a.types import TaskState, TaskStatusUpdateEvent

    mock_task = MagicMock()
    mock_task.artifacts = None

    incomplete_event = MagicMock(spec=TaskStatusUpdateEvent)
    incomplete_event.status = MagicMock()
    incomplete_event.status.state = TaskState.working
    incomplete_event.status.message = None

    async def mock_send_message(*args, **kwargs):
        yield (mock_task, incomplete_event)

    mock_a2a_client.get_card = AsyncMock(return_value=mock_agent_card)
    mock_a2a_client.send_message = mock_send_message

    with patch("strands.agent.a2a_agent.ClientFactory") as mock_factory_class:
        mock_factory_class.connect = AsyncMock(return_value=mock_a2a_client)

        events = []
        async for event in a2a_agent.stream_async("Hello"):
            events.append(event)

        # Should have 1 stream event + 1 result event (falls back to last)
        assert len(events) == 2
        assert "result" in events[1]
