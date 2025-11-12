"""BidiIO protocols for bidirectional streaming IO channels.

Defines callable protocols for input and output channels that can be used
with BidirectionalAgent. This approach provides better typing and flexibility
by separating input and output concerns into independent callables.
"""

from typing import Protocol, Awaitable

from .events import BidiInputEvent, BidiOutputEvent


class BidiInput(Protocol):
    """Protocol for bidirectional input callables.
    
    Input callables read data from a source (microphone, camera, websocket, etc.)
    and return events to be sent to the model.
    """

    def __call__(self) -> Awaitable[BidiInputEvent]:
        """Read input data from the source.
        
        Returns:
            Awaitable that resolves to an input event (audio, text, image, etc.)
        """
        ...


class BidiOutput(Protocol):
    """Protocol for bidirectional output callables.
    
    Output callables receive events from the model and handle them appropriately
    (play audio, display text, send over websocket, etc.).
    """

    def __call__(self, event: BidiOutputEvent) -> Awaitable[None]:
        """Process output event from the model.
        
        Args:
            event: Output event from the model (audio, text, tool calls, etc.)
        """
        ...