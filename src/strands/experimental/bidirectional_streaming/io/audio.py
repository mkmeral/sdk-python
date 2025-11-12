"""AudioIO - Clean separation of audio functionality from core BidirectionalAgent.

Provides audio input/output capabilities for BidirectionalAgent through callable protocols.
Handles all PyAudio setup, streaming, and cleanup while keeping the core agent data-agnostic.
"""

import asyncio
import base64
import logging
import pyaudio

from ..types.events import BidiAudioInputEvent, BidiAudioStreamEvent, BidiInterruptionEvent, BidiOutputEvent, BidiTranscriptStreamEvent

logger = logging.getLogger(__name__)


class AudioIO:
    """Audio IO channel for BidirectionalAgent with callable input/output.
    
    Provides input() and output() callables that can be passed to agent.run().
    """

    def __init__(
        self,
        audio_config: dict | None = None,
    ):
        """Initialize AudioIO with clean audio configuration.

        Args:
            audio_config: Dictionary containing audio configuration:
                - input_sample_rate (int): Microphone sample rate (default: 16000)
                - output_sample_rate (int): Speaker sample rate (default: 16000)
                - chunk_size (int): Audio chunk size in bytes (default: 512)
                - input_device_index (int): Specific input device (optional)
                - output_device_index (int): Specific output device (optional)
                - input_channels (int): Input channels (default: 1)
                - output_channels (int): Output channels (default: 1)
        """
        # Default audio configuration
        default_config = {
            "input_sample_rate": 16000,
            "output_sample_rate": 16000,
            "chunk_size": 512,
            "input_device_index": None,
            "output_device_index": None,
            "input_channels": 1,
            "output_channels": 1,
        }

        # Merge user config with defaults
        if audio_config:
            default_config.update(audio_config)

        # Set audio configuration attributes
        self.input_sample_rate = default_config["input_sample_rate"]
        self.output_sample_rate = default_config["output_sample_rate"]
        self.chunk_size = default_config["chunk_size"]
        self.input_device_index = default_config["input_device_index"]
        self.output_device_index = default_config["output_device_index"]
        self.input_channels = default_config["input_channels"]
        self.output_channels = default_config["output_channels"]

        # Audio infrastructure
        self.audio = None
        self.input_stream = None
        self.output_stream = None

    async def start(self) -> None:
        """Setup PyAudio streams for input and output."""
        if self.audio:
            return

        self.audio = pyaudio.PyAudio()

        self.input_stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=self.input_channels,
            rate=self.input_sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            input_device_index=self.input_device_index,
        )

        self.output_stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=self.output_channels,
            rate=self.output_sample_rate,
            output=True,
            frames_per_buffer=self.chunk_size,
            output_device_index=self.output_device_index,
        )

    async def stop(self) -> None:
        """Clean up IO channel resources."""
        if not self.audio:
            return

        if self.input_stream:
            self.input_stream.close()
        if self.output_stream:
            self.output_stream.close()
        
        self.audio.terminate()

        self.input_stream = None
        self.output_stream = None
        self.audio = None

    async def input(self) -> BidiAudioInputEvent:
        """Read audio from microphone (BidiInput callable).
        
        Automatically starts audio streams on first call if not already started.
        
        Returns:
            BidiAudioInputEvent with audio data from microphone.
        """
        # Lazy initialization - start on first use
        if not self.audio:
            await self.start()
        
        audio_bytes = self.input_stream.read(self.chunk_size, exception_on_overflow=False)

        return BidiAudioInputEvent(
            audio=base64.b64encode(audio_bytes).decode("utf-8"),
            format="pcm",
            sample_rate=self.input_sample_rate,
            channels=self.input_channels,
        )

    async def output(self, event: BidiOutputEvent) -> None:
        """Handle output events from model (BidiOutput callable).
        
        Automatically starts audio streams on first call if not already started.
        
        Args:
            event: Output event from the model to process.
        """
        # Lazy initialization - start on first use
        if not self.audio:
            await self.start()
        
        if isinstance(event, BidiAudioStreamEvent):
            self.output_stream.write(base64.b64decode(event["audio"]))
            # Yield control to prevent event loop hogging
            await asyncio.sleep(0.01)

        elif isinstance(event, BidiInterruptionEvent):
            logger.debug("Interruption detected - clearing audio buffer")
            await self._clear_audio_buffer()

        elif isinstance(event, BidiTranscriptStreamEvent):
            text = event["text"]
            if not event["is_final"]:
                text = f"Preview: {text}"
            print(text)

    async def _clear_audio_buffer(self) -> None:
        """Clear the audio output buffer on interruption.
        
        Stops and restarts the output stream to immediately clear any
        queued audio data, ensuring responsive interruption handling.
        """
        if not self.output_stream:
            return

        try:
            # Stop the stream to clear buffer
            if self.output_stream.is_active():
                self.output_stream.stop_stream()
            
            # Restart the stream
            self.output_stream.start_stream()
            logger.debug("Audio buffer cleared successfully")
        except Exception as e:
            logger.warning("Error clearing audio buffer: %s", e)