"""
Load persistent state into the current Python globals.

This script is injected before user code execution to restore previously
saved variables. Reads the pickled state file and updates the global
namespace with all stored variables.

If no state file exists (first execution), initializes with empty state.
This script is used by the execute_python operation when persist_state=True.

State is stored in persistent storage (Docker volumes or NFS) for durability across container restarts.

Note:
    The _state variable itself is private and not added to the user's
    visible namespace.
"""

import pickle
import os

# Determine state directory based on persistent storage availability and workflow_id
_workflow_id = os.getenv('WORKFLOW_ID', 'default')
_persistent_base = f'/persistent-storage/{_workflow_id}/state'

# Check if persistent storage mount is available
if os.path.exists('/persistent-storage') and os.path.ismount('/persistent-storage'):
    _state_dir = _persistent_base
    # Ensure workflow-specific subdirectory exists
    os.makedirs(_state_dir, exist_ok=True)
else:
    # Fall back to local storage
    _state_dir = '/tmp/sandbox_state'

_state_file = os.path.join(_state_dir, 'globals.pkl')

# Load previous state
try:
    with open(_state_file, 'rb') as f:
        _state = pickle.load(f)
    globals().update(_state)
except FileNotFoundError:
    _state = {}
