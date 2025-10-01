"""Bidirectional Agent for real-time streaming conversations.

Provides real-time audio and text interaction through persistent streaming sessions.
Unlike traditional request-response patterns, this agent maintains long-running 
conversations where users can interrupt, provide additional input, and receive 
continuous responses including audio output.

Key capabilities:
- Persistent conversation sessions with concurrent processing
- Real-time audio input/output streaming  
- Mid-conversation interruption and tool execution
- Event-driven communication with model providers
"""

import asyncio
import logging
from typing import AsyncIterable, List, Optional, Union

from strands.tools.executors import ConcurrentToolExecutor
from strands.tools.registry import ToolRegistry
from strands.types.content import Messages

from ..event_loop.bidirectional_event_loop import start_bidirectional_connection, stop_bidirectional_connection
from ..models.bidirectional_model import BidirectionalModel
from ..types.bidirectional_streaming import AudioInputEvent, BidirectionalStreamEvent, ImageInputEvent
from ..utils.debug import log_event, log_flow

logger = logging.getLogger(__name__)


class BidirectionalAgent:
    """Agent for bidirectional streaming conversations.
    
    Enables real-time audio and text interaction with AI models through persistent
    sessions. Supports concurrent tool execution and interruption handling.
    """
    
    def __init__(
        self,
        model: BidirectionalModel,
        tools: Optional[List] = None,
        system_prompt: Optional[str] = None,
        messages: Optional[Messages] = None
    ):
        """Initialize bidirectional agent with required model and optional configuration.
        
        Args:
            model: BidirectionalModel instance supporting streaming sessions.
            tools: Optional list of tools available to the model.
            system_prompt: Optional system prompt for conversations.
            messages: Optional conversation history to initialize with.
        """
        self.model = model
        self.system_prompt = system_prompt
        self.messages = messages or []
        
        # Initialize tool registry using existing Strands infrastructure
        self.tool_registry = ToolRegistry()
        if tools:
            self.tool_registry.process_tools(tools)
        self.tool_registry.initialize_tools()
        
        # Initialize tool executor for concurrent execution
        self.tool_executor = ConcurrentToolExecutor()
        
        # Session management
        self._session = None
        self._output_queue = asyncio.Queue()
    
    async def start(self) -> None:
        """Start a persistent bidirectional conversation session.
        
        Initializes the streaming session and starts background tasks for processing
        model events, tool execution, and session management.
        
        Raises:
            ValueError: If conversation already active.
            ConnectionError: If session creation fails.
        """
        if self._session and self._session.active:
            raise ValueError("Conversation already active. Call end() first.")
        
        log_flow("conversation_start", "initializing session")
        self._session = await start_bidirectional_connection(self)
        log_event("conversation_ready")
    
    async def send(self, input_data: Union[str, AudioInputEvent, ImageInputEvent]) -> None:
        """Send input to the model (text, audio, or image).
        
        Unified method for sending text, audio, and image input to the model during
        an active conversation session.
        
        Args:
            input_data: String for text, AudioInputEvent for audio, or ImageInputEvent for images.
            
        Raises:
            ValueError: If no active session or invalid input type.
        """
        self._validate_active_session()
        
        if isinstance(input_data, str):
            # Handle text input
            log_event("text_sent", length=len(input_data))
            await self._session.model_session.send_text_content(input_data)
        elif isinstance(input_data, dict) and "audioData" in input_data:
            # Handle audio input (AudioInputEvent)
            await self._session.model_session.send_audio_content(input_data)
        elif isinstance(input_data, dict) and "imageData" in input_data:
            # Handle image input (ImageInputEvent)
            log_event("image_sent", mime_type=input_data.get("mimeType"))
            await self._session.model_session.send_image_content(input_data)
        else:
            raise ValueError(
                "Input must be either a string (text), AudioInputEvent "
                "(dict with audioData, format, sampleRate, channels), or ImageInputEvent "
                "(dict with imageData, mimeType, encoding)"
            )
    

        
    async def receive(self) -> AsyncIterable[BidirectionalStreamEvent]:
        """Receive events from the model including audio, text, and tool calls.
        
        Yields model output events processed by background tasks including audio output,
        text responses, tool calls, and session updates.
        
        Yields:
            BidirectionalStreamEvent: Events from the model session.
        """
        while self._session and self._session.active:
            try:
                event = await asyncio.wait_for(self._output_queue.get(), timeout=0.1)
                yield event
            except asyncio.TimeoutError:
                continue
    
    async def interrupt(self) -> None:
        """Interrupt the current model generation and clear audio buffers.
        
        Sends interruption signal to stop generation immediately and clears 
        pending audio output for responsive conversation flow.
        
        Raises:
            ValueError: If no active session.
        """
        self._validate_active_session()
        await self._session.model_session.send_interrupt()
    
    async def end(self) -> None:
        """End the conversation session and cleanup all resources.
        
        Terminates the streaming session, cancels background tasks, and 
        closes the connection to the model provider.
        """
        if self._session:
            await stop_bidirectional_connection(self._session)
            self._session = None
    
    def _validate_active_session(self) -> None:
        """Validate that an active session exists.
        
        Raises:
            ValueError: If no active session.
        """
        if not self._session or not self._session.active:
            raise ValueError("No active conversation. Call start() first.")

