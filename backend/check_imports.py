try:
    from pydantic_ai import messages
    print("Available in pydantic_ai.messages:")
    print(dir(messages))
except ImportError as e:
    print(f"Import error: {e}")

try:
    import pydantic_ai
    print("Available in pydantic_ai:")
    print(dir(pydantic_ai))
except ImportError as e:
    print(f"Import error: {e}")