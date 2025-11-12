"""Unit tests for BidiAgent with callable IO."""

import asyncio
import pytest

from strands.experimental.bidirectional_streaming.agent.agent import BidiAgent
from strands.experimental.bidirectional_streaming.types.events import (
    BidiAudioInputEvent,
    BidiTextInputEvent,
    BidiTranscriptStreamEvent,
)


class TestAgentRunValidation:
    """Test BidiAgent.run() parameter validation."""

    @pytest.mark.asyncio
    async def test_run_requires_inputs(self):
        """Test that run() requires at least one input."""
        agent = BidiAgent()
        
        async def dummy_output(event):
            pass
        
        with pytest.raises(ValueError, match="inputs parameter cannot be empty"):
            await agent.run(inputs=[], outputs=[dummy_output])

    @pytest.mark.asyncio
    async def test_run_requires_outputs(self):
        """Test that run() requires at least one output."""
        agent = BidiAgent()
        
        async def dummy_input():
            return BidiTextInputEvent(text="test", role="user")
        
        with pytest.raises(ValueError, match="outputs parameter cannot be empty"):
            await agent.run(inputs=[dummy_input], outputs=[])




class TestCallableProtocols:
    """Test that callables match the protocol signatures."""

    @pytest.mark.asyncio
    async def test_input_callable_signature(self):
        """Test input callable returns BidiInputEvent."""
        
        async def valid_input():
            return BidiTextInputEvent(text="test", role="user")
        
        result = await valid_input()
        assert isinstance(result, BidiTextInputEvent)

    @pytest.mark.asyncio
    async def test_output_callable_signature(self):
        """Test output callable accepts BidiOutputEvent."""
        
        received = None
        
        async def valid_output(event):
            nonlocal received
            received = event
        
        event = BidiTranscriptStreamEvent(
            delta={"text": "test"},
            text="test",
            role="assistant",
            is_final=True,
            current_transcript="test"
        )
        
        await valid_output(event)
        assert received == event


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
