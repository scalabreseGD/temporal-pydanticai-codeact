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

    # Create dict of variable names and their types
    var_info = {name: type(value).__name__ for name, value in state.items()}

    import json
    print(json.dumps(var_info))
except Exception as e:
    import json
    print(json.dumps({"error": str(e)}))
