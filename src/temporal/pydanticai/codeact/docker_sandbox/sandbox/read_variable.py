"""
Read a specific variable from the persistent state.

Takes a variable name as a command-line argument and returns its value
and type as JSON. Handles serialization of both simple and complex types.

Usage:
    python read_variable.py variable_name

Args (command-line):
    variable_name: Name of the variable to retrieve

Output:
    JSON object with:
    - success: bool indicating if variable was found
    - value: The variable's value (serialized if complex type)
    - type: The variable's type name
    - error: Error message if operation failed
    - note: Additional information about serialization

Example output:
    {"success": true, "value": 42, "type": "int"}
    {"success": false, "error": "Variable 'foo' not found in state"}
"""

import pickle
import json
import sys
import os

# Determine state directory based on persistent storage availability and workflow_id
workflow_id = os.getenv('WORKFLOW_ID', 'default')
persistent_base = f'/persistent-storage/{workflow_id}/state'

# Check if persistent storage mount is available
if os.path.exists('/persistent-storage') and os.path.ismount('/persistent-storage'):
    state_dir = persistent_base
else:
    # Fall back to local storage
    state_dir = '/tmp/sandbox_state'

state_file = os.path.join(state_dir, 'globals.pkl')

try:
    with open(state_file, 'rb') as f:
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
