"""
List all variables in the persistent state with their types.

Reads the persistent state and returns a JSON mapping of variable names
to their type names (e.g., {"x": "int", "data": "DataFrame"}).

Output:
    JSON object mapping variable names to type strings, or error object
    if state cannot be read.

Example output:
    {"x": "int", "y": "float", "data": "list", "model": "LinearRegression"}
"""

import pickle

try:
    with open('/tmp/sandbox_state/globals.pkl', 'rb') as f:
        state = pickle.load(f)

    # Create dict of variable names and their types
    var_info = {name: type(value).__name__ for name, value in state.items()}

    import json
    print(json.dumps(var_info))
except Exception as e:
    import json
    print(json.dumps({"error": str(e)}))
