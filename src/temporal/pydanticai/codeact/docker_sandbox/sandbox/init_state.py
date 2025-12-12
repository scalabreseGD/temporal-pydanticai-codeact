"""
Initialize persistent state storage for sandbox containers.

Creates the state directory and initializes an empty pickled state file.
This script is executed once during container startup to set up the
persistent variable storage system.

The state file stores Python variables across code executions, enabling
stateful REPL-like behavior within the sandbox. State is stored in
persistent storage (Docker volumes or NFS) for durability across container restarts.
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

# Create state directory
os.makedirs(state_dir, exist_ok=True)

# Initialize empty state
state = {}
state_file = os.path.join(state_dir, 'globals.pkl')
with open(state_file, 'wb') as f:
    pickle.dump(state, f)

print(f"State initialized at: {state_file}")
