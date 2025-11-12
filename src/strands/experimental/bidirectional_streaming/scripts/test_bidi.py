"""Test BidirectionalAgent with simple developer experience."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from strands.experimental.bidirectional_streaming.agent.agent import BidiAgent
from strands.experimental.bidirectional_streaming.models.novasonic import BidiNovaSonicModel
from strands.experimental.bidirectional_streaming.io.audio import AudioIO
from strands_tools import calculator


async def main():
    """Test the BidirectionalAgent API with callable IO."""
    
    # Create audio IO
    audio_io = AudioIO()
    
    # Nova Sonic model
    model = BidiNovaSonicModel(region="us-east-1")

    try:
        async with BidiAgent(model=model, tools=[calculator]) as agent:
            print("🎤 BidiAgent with Nova Sonic")
            print("Try asking: 'What is 25 times 8?' or 'Calculate the square root of 144'")
            print("Press Ctrl+C to stop\n")
            
            # Run with callable inputs and outputs
            await agent.run(
                inputs=[audio_io.input],
                outputs=[audio_io.output]
            )
    except KeyboardInterrupt:
        print("\n⏹️ Stopping...")
    finally:
        # Clean up audio resources
        print("🧹 Cleaning up...")
        await audio_io.stop()
        print("✅ Done")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Conversation ended by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
