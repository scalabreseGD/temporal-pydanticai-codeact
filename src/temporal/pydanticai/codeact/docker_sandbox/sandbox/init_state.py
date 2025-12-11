"""
Initialize persistent state storage for sandbox containers.

Creates the state directory and initializes an empty pickled state file.
This script is executed once during container startup to set up the
persistent variable storage system.

The state file stores Python variables across code executions, enabling
stateful REPL-like behavior within the sandbox.
"""

import pickle
import os

# Create state directory
os.makedirs('/tmp/sandbox_state', exist_ok=True)

# Initialize empty state
state = {}
with open('/tmp/sandbox_state/globals.pkl', 'wb') as f:
    pickle.dump(state, f)
