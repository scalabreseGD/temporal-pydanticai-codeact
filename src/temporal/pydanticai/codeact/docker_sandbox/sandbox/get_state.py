"""
Retrieve the complete persistent state from the sandbox container.

Combines the functionality of list_variables.py and read_variable.py to
provide a comprehensive view of all variables with their types and values.

Reads the persistent state and returns a JSON object containing:
- A dictionary of variable names mapped to objects with type and value info

Output:
    JSON object with variable information, or error object if state cannot be read.

Example output:
    {
        "x": {"type": "int", "value": 42},
        "data": {"type": "list", "value": [1, 2, 3, 4, 5]},
        "model": {"type": "LinearRegression", "value": "LinearRegression(...)"}
    }
"""

import pickle
import json

try:
    with open('/tmp/sandbox_state/globals.pkl', 'rb') as f:
        state = pickle.load(f)

    # Build comprehensive state info with types and values
    state_info = {}

    for name, value in state.items():
        try:
            # For simple types, use the value directly
            if isinstance(value, (int, float, str, bool, list, dict, tuple, type(None))):
                serialized_value = value
            else:
                # For complex types, convert to string representation
                serialized_value = str(value)

            state_info[name] = {
                "type": type(value).__name__,
                "value": serialized_value
            }
        except Exception as e:
            # Fallback for values that can't be serialized
            state_info[name] = {
                "type": type(value).__name__,
                "value": str(value),
                "note": "Value serialized as string"
            }

    print(json.dumps(state_info))

except Exception as e:
    print(json.dumps({"error": str(e)}))
