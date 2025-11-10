"""Unit tests for bidirectional streaming event loop."""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch

from strands.experimental.bidirectional_streaming.event_loop.bidirectional_event_loop import (
    BidirectionalConnection,
    _handle_model_event,
    _handle_connection_error,
    _is_reconnectable_error,
    _reconnect_session,
)


class TestHandleModelEvent:
    """Test individual model event handling."""

    @pytest.mark.asyncio
    async def test_handle_interruption_event(self):
        """Interruption events should trigger interruption handling."""
        mock_model = AsyncMock()
        mock_agent = Mock()
        mock_agent._output_queue = asyncio.Queue()
        
        session = BidirectionalConnection(model=mock_model, agent=mock_agent)
        session.interruption_lock = asyncio.Lock()
        session.interrupted = False
        session.pending_tool_tasks = {}
        session.audio_output_queue = asyncio.Queue()
        
        event = {"type": "bidirectional_interruption", "reason": "user_speech"}
        
        await _handle_model_event(session, event)
        
        # Event should be forwarded to output queue
        output_event = await session.agent._output_queue.get()
        assert output_event["type"] == "bidirectional_interruption"

    @pytest.mark.asyncio
    async def test_handle_tool_use_event(self):
        """Tool use events should be queued for execution."""
        mock_model = AsyncMock()
        mock_agent = Mock()
        mock_agent._output_queue = asyncio.Queue()
        
        session = BidirectionalConnection(model=mock_model, agent=mock_agent)
        session.tool_queue = asyncio.Queue()
        
        event = {
            "type": "tool_use_stream",
            "current_tool_use": {
                "name": "calculator",
                "toolUseId": "tool-123",
                "input": {"expression": "2+2"}
            }
        }
        
        await _handle_model_event(session, event)
        
        # Tool should be queued
        tool_use = await asyncio.wait_for(session.tool_queue.get(), timeout=1.0)
        assert tool_use["name"] == "calculator"
        
        # Event should be forwarded to output queue
        output_event = await session.agent._output_queue.get()
        assert "current_tool_use" in output_event

    @pytest.mark.asyncio
    async def test_handle_transcript_event_user(self):
        """User transcript events should update conversation history."""
        mock_model = AsyncMock()
        mock_agent = Mock()
        mock_agent._output_queue = asyncio.Queue()
        mock_agent.messages = []
        
        session = BidirectionalConnection(model=mock_model, agent=mock_agent)
        
        event = {
            "type": "bidirectional_transcript_stream",
            "source": "user",
            "text": "Hello world",
            "is_final": True
        }
        
        await _handle_model_event(session, event)
        
        # User message should be added to history
        assert len(session.agent.messages) == 1
        assert session.agent.messages[0]["role"] == "user"
        assert session.agent.messages[0]["content"] == "Hello world"
        
        # Event should be forwarded to output queue
        output_event = await session.agent._output_queue.get()
        assert output_event["type"] == "bidirectional_transcript_stream"

    @pytest.mark.asyncio
    async def test_handle_transcript_event_assistant(self):
        """Assistant transcript events should not update history."""
        mock_model = AsyncMock()
        mock_agent = Mock()
        mock_agent._output_queue = asyncio.Queue()
        mock_agent.messages = []
        
        session = BidirectionalConnection(model=mock_model, agent=mock_agent)
        
        event = {
            "type": "bidirectional_transcript_stream",
            "source": "assistant",
            "text": "Hello back",
            "is_final": True
        }
        
        await _handle_model_event(session, event)
        
        # Assistant messages should not be added to history
        assert len(session.agent.messages) == 0
        
        # Event should still be forwarded
        output_event = await session.agent._output_queue.get()
        assert output_event["type"] == "bidirectional_transcript_stream"

    @pytest.mark.asyncio
    async def test_handle_audio_stream_event(self):
        """Audio stream events should be forwarded to output queue."""
        mock_model = AsyncMock()
        mock_agent = Mock()
        mock_agent._output_queue = asyncio.Queue()
        
        session = BidirectionalConnection(model=mock_model, agent=mock_agent)
        
        event = {
            "type": "bidirectional_audio_stream",
            "audio": "base64data",
            "format": "pcm",
            "sample_rate": 16000,
            "channels": 1
        }
        
        await _handle_model_event(session, event)
        
        # Event should be forwarded
        output_event = await session.agent._output_queue.get()
        assert output_event["type"] == "bidirectional_audio_stream"
        assert output_event["audio"] == "base64data"


class TestReconnectableErrorDetection:
    """Test error type detection for reconnection."""

    def test_connection_error_is_reconnectable(self):
        """ConnectionError should be reconnectable."""
        error = ConnectionError("Connection lost")
        assert _is_reconnectable_error(error) is True

    def test_connection_reset_error_is_reconnectable(self):
        """ConnectionResetError should be reconnectable."""
        error = ConnectionResetError("Connection reset by peer")
        assert _is_reconnectable_error(error) is True

    def test_broken_pipe_error_is_reconnectable(self):
        """BrokenPipeError should be reconnectable."""
        error = BrokenPipeError("Broken pipe")
        assert _is_reconnectable_error(error) is True

    def test_value_error_not_reconnectable(self):
        """ValueError should not be reconnectable."""
        error = ValueError("Invalid value")
        assert _is_reconnectable_error(error) is False

    def test_runtime_error_not_reconnectable(self):
        """RuntimeError should not be reconnectable."""
        error = RuntimeError("Runtime error")
        assert _is_reconnectable_error(error) is False


class TestReconnectSession:
    """Test session reconnection logic."""

    @pytest.mark.asyncio
    async def test_reconnect_success_first_attempt(self):
        """Reconnection should succeed on first attempt."""
        mock_model = AsyncMock()
        mock_model.close = AsyncMock()
        mock_model.connect = AsyncMock()
        
        mock_agent = Mock()
        mock_agent.system_prompt = "test prompt"
        mock_agent.messages = []
        mock_agent.max_reconnection_attempts = 3
        mock_agent.tool_registry = Mock()
        mock_agent.tool_registry.get_all_tool_specs = Mock(return_value=[])
        
        session = BidirectionalConnection(model=mock_model, agent=mock_agent)
        
        await _reconnect_session(session)
        
        # Verify close and connect were called
        mock_model.close.assert_called_once()
        mock_model.connect.assert_called_once_with(
            system_prompt="test prompt",
            tools=[],
            messages=[]
        )

    @pytest.mark.asyncio
    async def test_reconnect_success_after_retries(self):
        """Reconnection should succeed after failed attempts."""
        mock_model = AsyncMock()
        mock_model.close = AsyncMock()
        mock_model.connect = AsyncMock(
            side_effect=[
                ConnectionError("Failed 1"),
                ConnectionError("Failed 2"),
                None  # Success
            ]
        )
        
        mock_agent = Mock()
        mock_agent.system_prompt = "test prompt"
        mock_agent.messages = []
        mock_agent.max_reconnection_attempts = 3
        mock_agent.tool_registry = Mock()
        mock_agent.tool_registry.get_all_tool_specs = Mock(return_value=[])
        
        session = BidirectionalConnection(model=mock_model, agent=mock_agent)
        
        await _reconnect_session(session)
        
        # Should have tried 3 times
        assert mock_model.connect.call_count == 3

    @pytest.mark.asyncio
    async def test_reconnect_fails_after_max_attempts(self):
        """Reconnection should fail after max attempts."""
        mock_model = AsyncMock()
        mock_model.close = AsyncMock()
        mock_model.connect = AsyncMock(side_effect=ConnectionError("Always fails"))
        
        mock_agent = Mock()
        mock_agent.system_prompt = "test prompt"
        mock_agent.messages = []
        mock_agent.max_reconnection_attempts = 3
        mock_agent.tool_registry = Mock()
        mock_agent.tool_registry.get_all_tool_specs = Mock(return_value=[])
        
        session = BidirectionalConnection(model=mock_model, agent=mock_agent)
        
        with pytest.raises(ConnectionError):
            await _reconnect_session(session)
        
        # Should have tried exactly 3 times
        assert mock_model.connect.call_count == 3

    @pytest.mark.asyncio
    async def test_reconnect_respects_max_attempts_config(self):
        """Reconnection should respect configured max_reconnection_attempts."""
        mock_model = AsyncMock()
        mock_model.close = AsyncMock()
        mock_model.connect = AsyncMock(side_effect=ConnectionError("Always fails"))
        
        mock_agent = Mock()
        mock_agent.system_prompt = "test prompt"
        mock_agent.messages = []
        mock_agent.max_reconnection_attempts = 5  # Custom value
        mock_agent.tool_registry = Mock()
        mock_agent.tool_registry.get_all_tool_specs = Mock(return_value=[])
        
        session = BidirectionalConnection(model=mock_model, agent=mock_agent)
        
        with pytest.raises(ConnectionError):
            await _reconnect_session(session)
        
        # Should have tried exactly 5 times (not 3)
        assert mock_model.connect.call_count == 5


class TestHandleConnectionError:
    """Test connection error handling logic."""

    @pytest.mark.asyncio
    async def test_reconnectable_error_with_reconnection_enabled(self):
        """Should reconnect when error is reconnectable and feature is enabled."""
        mock_model = AsyncMock()
        mock_model.close = AsyncMock()
        mock_model.connect = AsyncMock()
        
        mock_agent = Mock()
        mock_agent.enable_reconnection = True
        mock_agent.max_reconnection_attempts = 3
        mock_agent.system_prompt = "test prompt"
        mock_agent.messages = []
        mock_agent.tool_registry = Mock()
        mock_agent.tool_registry.get_all_tool_specs = Mock(return_value=[])
        
        session = BidirectionalConnection(model=mock_model, agent=mock_agent)
        
        error = ConnectionError("Connection lost")
        result = await _handle_connection_error(session, error)
        
        assert result is True
        assert session.active is True
        mock_model.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconnectable_error_with_reconnection_disabled(self):
        """Should not reconnect when feature is disabled."""
        mock_model = AsyncMock()
        mock_agent = Mock()
        mock_agent.enable_reconnection = False
        
        session = BidirectionalConnection(model=mock_model, agent=mock_agent)
        
        error = ConnectionError("Connection lost")
        result = await _handle_connection_error(session, error)
        
        assert result is False
        assert session.active is False
        mock_model.connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_reconnectable_error(self):
        """Should not reconnect for non-reconnectable errors."""
        mock_model = AsyncMock()
        mock_agent = Mock()
        mock_agent.enable_reconnection = True
        
        session = BidirectionalConnection(model=mock_model, agent=mock_agent)
        
        error = ValueError("Invalid value")
        result = await _handle_connection_error(session, error)
        
        assert result is False
        assert session.active is False
        mock_model.connect.assert_not_called()
