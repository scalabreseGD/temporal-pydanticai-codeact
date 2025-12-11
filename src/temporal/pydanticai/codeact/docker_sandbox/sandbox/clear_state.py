"""
Clear all variables from the persistent state.

Resets the persistent state to an empty dictionary, removing all stored
variables. This is useful for starting fresh without restarting the container.

Output:
    Prints "State cleared" confirmation message to stdout.
"""

import pickle

state = {}
with open('/tmp/sandbox_state/globals.pkl', 'wb') as f:
    pickle.dump(state, f)
print("State cleared")
