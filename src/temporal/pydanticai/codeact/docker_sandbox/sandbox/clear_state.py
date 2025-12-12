"""
Clear all variables from the persistent state.

Resets the persistent state to an empty dictionary, removing all stored
variables. This is useful for starting fresh without restarting the container.

Output:
    Prints "State cleared" confirmation message to stdout.
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

state = {}
with open(state_file, 'wb') as f:
    pickle.dump(state, f)
print("State cleared")
