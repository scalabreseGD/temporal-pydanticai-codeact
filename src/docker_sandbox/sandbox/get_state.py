"""
Retrieve the complete persistent state from the sandbox container.

Reads and prints the entire pickled state dictionary containing all
persisted variables. Returns an empty dict if state file doesn't exist
or cannot be read.

Output:
    Prints the state dictionary to stdout for capture by the container
    management system.
"""

import pickle
try:
    with open('/tmp/sandbox_state/globals.pkl', 'rb') as f:
        state = pickle.load(f)
    print(state)
except Exception as e:
    print({})
