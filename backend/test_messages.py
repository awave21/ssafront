
import asyncio
from pydantic import TypeAdapter
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemMessage,
    UserMessage,
    TextPart,
    ToolCallPart,
    ToolReturnPart
)

# Define the adapter as in the code
messages_adapter = TypeAdapter(list[ModelMessage | ModelRequest | ModelResponse | SystemMessage | UserMessage])

async def test_serialization():
    print("Testing serialization...")
    
    # Create some dummy messages
    msgs = [
        SystemMessage(content="You are a helper."),
        UserMessage(content="Hello"),
        ModelResponse(parts=[TextPart(content="Hi there!")]),
        ModelRequest(parts=[ToolCallPart(tool_name="test_tool", args={"a": 1}, tool_call_id="123")]),
        UserMessage(content="tool output", timestamp=None) # Simulating tool return, though usually it's inside UserMessage or ToolReturnMessage depending on version
    ]
    
    # Try to dump
    try:
        json_data = messages_adapter.dump_python(msgs, mode="json")
        print("Dump successful")
        print(json_data)
    except Exception as e:
        print(f"Dump failed: {e}")
        return

    # Try to validate back
    try:
        restored_msgs = messages_adapter.validate_python(json_data)
        print("Restore successful")
        print(restored_msgs)
    except Exception as e:
        print(f"Restore failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_serialization())
