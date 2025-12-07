import pickle
import json
import sys

try:
    with open('/tmp/sandbox_state/globals.pkl', 'rb') as f:
        state = pickle.load(f)

    # Variable name should be passed as command line argument
    variable_name = sys.argv[1] if len(sys.argv) > 1 else None

    if variable_name is None:
        result = {
            "success": False,
            "error": "No variable name provided"
        }
    elif variable_name not in state:
        result = {
            "success": False,
            "error": f"Variable '{variable_name}' not found in state"
        }
    else:
        value = state[variable_name]

        # Try to serialize the value
        try:
            # For simple types, use the value directly
            if isinstance(value, (int, float, str, bool, list, dict, tuple, type(None))):
                serialized_value = value
            else:
                # For complex types, convert to string representation
                serialized_value = str(value)

            result = {
                "success": True,
                "value": serialized_value,
                "type": type(value).__name__
            }
        except Exception as e:
            result = {
                "success": True,
                "value": str(value),
                "type": type(value).__name__,
                "note": "Value serialized as string"
            }

    print(json.dumps(result))

except Exception as e:
    result = {
        "success": False,
        "error": str(e)
    }
    print(json.dumps(result))
