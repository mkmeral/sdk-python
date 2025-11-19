"""Parameterized integration tests for bidirectional streaming.

Tests fundamental functionality across multiple model providers (Nova Sonic, OpenAI, etc.)
including multi-turn conversations, audio I/O, text transcription, and tool execution.

This demonstrates the provider-agnostic design of the bidirectional streaming system.
"""

import asyncio
import logging
import os

import pytest

from strands import tool
from strands.experimental.bidi.agent.agent import BidiAgent
from strands.experimental.bidi.models.gemini_live import BidiGeminiLiveModel
from strands.experimental.bidi.models.novasonic import BidiNovaSonicModel
from strands.experimental.bidi.models.openai import BidiOpenAIRealtimeModel

from .context import BidirectionalTestContext

logger = logging.getLogger(__name__)


# Simple calculator tool for testing
@tool
def calculator(operation: str, x: float, y: float) -> float:
    """Perform basic arithmetic operations.

    Args:
        operation: The operation to perform (add, subtract, multiply, divide)
        x: First number
        y: Second number

    Returns:
        Result of the operation
    """
    if operation == "add":
        return x + y
    elif operation == "subtract":
        return x - y
    elif operation == "multiply":
        return x * y
    elif operation == "divide":
        if y == 0:
            raise ValueError("Cannot divide by zero")
        return x / y
    else:
        raise ValueError(f"Unknown operation: {operation}")


# Provider configurations
PROVIDER_CONFIGS = {
    "nova_sonic": {
        "model_class": BidiNovaSonicModel,
        "model_kwargs": {"region": "us-east-1"},
        "silence_duration": 2.5,  # Nova Sonic needs 2+ seconds of silence
        "env_vars": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
        "skip_reason": "AWS credentials not available",
    },
    "openai": {
        "model_class": BidiOpenAIRealtimeModel,
        "model_kwargs": {
            "model": "gpt-4o-realtime-preview-2024-12-17",
            "session": {
                "output_modalities": ["audio"],  # OpenAI only supports audio OR text, not both
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": 24000},
                        "turn_detection": {
                            "type": "server_vad",
                            "threshold": 0.5,
                            "silence_duration_ms": 700,
                        },
                    },
                    "output": {"format": {"type": "audio/pcm", "rate": 24000}, "voice": "alloy"},
                },
            },
        },
        "silence_duration": 1.0,  # OpenAI has faster VAD
        "env_vars": ["OPENAI_API_KEY"],
        "skip_reason": "OPENAI_API_KEY not available",
    },
    "gemini_live": {
        "model_class": BidiGeminiLiveModel,
        "model_kwargs": {
            # Uses default model and config (audio output + transcription enabled)
        },
        "silence_duration": 1.5,  # Gemini has good VAD, similar to OpenAI
        "env_vars": ["GOOGLE_AI_API_KEY"],
        "skip_reason": "GOOGLE_AI_API_KEY not available",
    },
}


def check_provider_available(provider_name: str) -> tuple[bool, str]:
    """Check if a provider's credentials are available.

    Args:
        provider_name: Name of the provider to check.

    Returns:
        Tuple of (is_available, skip_reason).
    """
    config = PROVIDER_CONFIGS[provider_name]
    env_vars = config["env_vars"]

    missing_vars = [var for var in env_vars if not os.getenv(var)]

    if missing_vars:
        return False, f"{config['skip_reason']}: {', '.join(missing_vars)}"

    return True, ""


@pytest.fixture(params=list(PROVIDER_CONFIGS.keys()))
def provider_config(request):
    """Provide configuration for each model provider.

    This fixture is parameterized to run tests against all available providers.
    """
    provider_name = request.param
    config = PROVIDER_CONFIGS[provider_name]

    # Check if provider is available
    is_available, skip_reason = check_provider_available(provider_name)
    if not is_available:
        pytest.skip(skip_reason)

    return {
        "name": provider_name,
        **config,
    }


@pytest.fixture
def agent_with_calculator(provider_config):
    """Provide bidirectional agent with calculator tool for the given provider.

    Note: Session lifecycle (start/end) is handled by BidirectionalTestContext.
    """
    model_class = provider_config["model_class"]
    model_kwargs = provider_config["model_kwargs"]

    model = model_class(**model_kwargs)
    return BidiAgent(
        model=model,
        tools=[calculator],
        system_prompt="You are a helpful assistant with access to a calculator tool. Keep responses brief.",
    )


@pytest.mark.asyncio
async def test_bidirectional_agent(agent_with_calculator, audio_generator, provider_config):
    """Test multi-turn conversation with follow-up questions across providers.

    This test runs against all configured providers (Nova Sonic, OpenAI, etc.)
    to validate provider-agnostic functionality.

    Validates:
    - Session lifecycle (start/end via context manager)
    - Audio input streaming
    - Speech-to-text transcription
    - Tool execution (calculator)
    - Multi-turn conversation flow
    - Text-to-speech audio output
    """
    provider_name = provider_config["name"]
    silence_duration = provider_config["silence_duration"]

    logger.info("provider=<%s> | testing provider", provider_name)

    async with BidirectionalTestContext(agent_with_calculator, audio_generator) as ctx:
        # Turn 1: Simple greeting to test basic audio I/O
        await ctx.say("Hello, can you hear me?")
        # Wait for silence to trigger provider's VAD/silence detection
        await asyncio.sleep(silence_duration)
        await ctx.wait_for_response()

        text_outputs_turn1 = ctx.get_text_outputs()

        # Validate turn 1 - just check we got a response
        assert len(text_outputs_turn1) > 0, f"[{provider_name}] No text output received in turn 1"

        logger.info("provider=<%s> | turn 1 complete received response", provider_name)
        logger.info("provider=<%s>, response=<%s> | turn 1 response", provider_name, text_outputs_turn1[0][:100])

        # Turn 2: Follow-up to test multi-turn conversation
        await ctx.say("What's your name?")
        # Wait for silence to trigger provider's VAD/silence detection
        await asyncio.sleep(silence_duration)
        await ctx.wait_for_response()

        text_outputs_turn2 = ctx.get_text_outputs()

        # Validate turn 2 - check we got more responses
        assert len(text_outputs_turn2) > len(text_outputs_turn1), f"[{provider_name}] No new text output in turn 2"

        logger.info("provider=<%s> | turn 2 complete multi-turn conversation works", provider_name)
        logger.info("provider=<%s>, response_count=<%d> | total responses", provider_name, len(text_outputs_turn2))

        # Validate full conversation
        # Validate audio outputs
        audio_outputs = ctx.get_audio_outputs()
        assert len(audio_outputs) > 0, f"[{provider_name}] No audio output received"
        total_audio_bytes = sum(len(audio) for audio in audio_outputs)

        # Summary
        logger.info("=" * 60)
        logger.info("provider=<%s> | multi-turn conversation test passed", provider_name)
        logger.info("provider=<%s> | test summary", provider_name)
        logger.info("event_count=<%d> | total events", len(ctx.get_events()))
        logger.info("text_response_count=<%d> | text responses", len(text_outputs_turn2))
        logger.info(
            "audio_chunk_count=<%d>, audio_bytes=<%d> | audio chunks",
            len(audio_outputs),
            total_audio_bytes,
        )
        logger.info("=" * 60)



@pytest.mark.asyncio
async def test_bidi_agent_rejects_agent_only_tool():
    """Test that BidiAgent rejects tools with Agent-only ToolContext.

    This validates the tool compatibility validation system that prevents
    BidiAgent from using tools that are only compatible with Agent.
    """
    from strands import ToolContext

    # Define a tool that only works with Agent (uses ToolContext)
    @tool(context=True)
    def agent_only_tool(tool_context: ToolContext) -> dict:
        """Tool that only works with Agent."""
        return {"status": "success", "content": [{"text": f"Agent: {tool_context.agent.name}"}]}

    # Attempt to create BidiAgent with Agent-only tool should fail
    with pytest.raises(TypeError) as exc_info:
        BidiAgent(tools=[agent_only_tool])

    error_msg = str(exc_info.value)
    assert "BidiAgent cannot use the following tools" in error_msg
    assert "agent_only_tool" in error_msg
    assert "BaseToolContext[Agent | BidiAgent]" in error_msg

    logger.info("✓ BidiAgent correctly rejected Agent-only tool")
    logger.info("error_message=<%s>", error_msg.split("\n")[0])


@pytest.mark.asyncio
async def test_bidi_agent_accepts_universal_tool():
    """Test that BidiAgent accepts tools with BaseToolContext[Agent | BidiAgent].

    This validates that tools explicitly marked as universal can be used
    with both Agent and BidiAgent.
    """
    from strands import Agent, BaseToolContext

    # Define a universal tool that works with both agents
    @tool(context=True)
    def universal_tool(tool_context: BaseToolContext[Agent | BidiAgent]) -> dict:
        """Tool that works with both Agent and BidiAgent."""
        state_value = tool_context.agent.state.get("test_key", "default")
        return {"status": "success", "content": [{"text": f"State: {state_value}"}]}

    # Creating BidiAgent with universal tool should succeed
    agent = BidiAgent(tools=[universal_tool])
    assert "universal_tool" in agent.tool_names

    logger.info("✓ BidiAgent correctly accepted universal tool")


@pytest.mark.asyncio
async def test_bidi_agent_accepts_simple_tool():
    """Test that BidiAgent accepts tools without context parameter.

    This validates that simple tools (without context parameter) work
    with all agent types automatically.
    """

    # Define a simple tool without context parameter
    @tool
    def simple_calculator(x: int, y: int) -> dict:
        """Add two numbers."""
        return {"status": "success", "content": [{"text": str(x + y)}]}

    # Creating BidiAgent with simple tool should succeed
    agent = BidiAgent(tools=[simple_calculator])
    assert "simple_calculator" in agent.tool_names

    logger.info("✓ BidiAgent correctly accepted simple tool without context")
