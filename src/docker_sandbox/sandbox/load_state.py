"""
Load persistent state into the current Python globals.

This script is injected before user code execution to restore previously
saved variables. Reads the pickled state file and updates the global
namespace with all stored variables.

If no state file exists (first execution), initializes with empty state.
This script is used by the execute_python operation when persist_state=True.

Note:
    The _state variable itself is private and not added to the user's
    visible namespace.
"""

import pickle

# Load previous state
try:
    with open('/tmp/sandbox_state/globals.pkl', 'rb') as f:
        _state = pickle.load(f)
    globals().update(_state)
except FileNotFoundError:
    _state = {}
